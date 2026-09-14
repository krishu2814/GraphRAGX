"""Unit tests for entity extraction, relationship extraction, and entity resolution."""

from pathlib import Path
import pytest

from app.ingestion.chunker import DocumentChunk, SemanticChunker
from app.ingestion.entity_extractor import EntityExtractor
from app.ingestion.entity_resolution import EntityResolver
from app.ingestion.loaders import MarkdownLoader
from app.ingestion.relation_extractor import RelationExtractor
from app.models.entities import CanonicalEntity, Entity, EntityType
from app.models.relationships import Evidence, Relationship, RelationType

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"


@pytest.fixture
def sample_chunk():
    """Create a representative document chunk for extraction testing."""
    from app.ingestion.metadata import AccessTier, ChunkMetadata

    meta = ChunkMetadata(
        document_id="customer_acme",
        title="Customer Case Profile: Acme Corp",
        department="Customer Success",
        access_tier=AccessTier.CONFIDENTIAL,
        version="3.2",
        section_title="Licensed Solutions & Architecture",
        section_path="Customer Case Profile: Acme Corp > Licensed Solutions & Architecture",
        char_count=320,
        word_count=45,
        estimated_tokens=80,
    )
    text = (
        "Acme Corp relies on Product Nova deployed in a dedicated AWS VPC. "
        "Product Nova delegates all user authentication to Identity Service. "
        "Following Version 3.2, Identity Service strictly enforces OAuth 2.1."
    )
    return DocumentChunk(
        chunk_id="chunk_customer_acme_001",
        document_id="customer_acme",
        text=text,
        index=1,
        metadata=meta,
    )


class TestEntityExtractor:
    """Test suite for EntityExtractor in deterministic rule mode."""

    def test_extract_entities_from_chunk(self, sample_chunk):
        extractor = EntityExtractor(use_llm_if_available=False)
        entities = extractor.extract(sample_chunk)

        entity_names = {e.name for e in entities}
        assert "Acme Corp" in entity_names
        assert "Product Nova" in entity_names
        assert "Identity Service" in entity_names
        assert "AWS" in entity_names
        assert "Version 3.2" in entity_names
        assert "OAuth 2.1" in entity_names

        # Check entity types
        for e in entities:
            if e.name == "Acme Corp":
                assert e.type == EntityType.CUSTOMER
            elif e.name == "Product Nova":
                assert e.type == EntityType.PRODUCT
            elif e.name == "Identity Service":
                assert e.type == EntityType.SERVICE
            elif e.name == "Version 3.2":
                assert e.type == EntityType.VERSION
            elif e.name == "OAuth 2.1":
                assert e.type == EntityType.TECHNOLOGY


class TestRelationExtractor:
    """Test suite for RelationExtractor with grounded evidence."""

    def test_extract_relationships_from_chunk(self, sample_chunk):
        extractor = RelationExtractor(use_llm_if_available=False)
        relations = extractor.extract(sample_chunk)

        assert len(relations) >= 2

        # Check that relations have grounded evidence
        for rel in relations:
            assert len(rel.evidence) >= 1
            ev = rel.evidence[0]
            assert ev.chunk_id == sample_chunk.chunk_id
            assert ev.document_id == sample_chunk.document_id
            assert len(ev.text) > 10
            assert ev.confidence > 0.0

        # Verify key relationship types found in the sample text
        rel_types = {r.type for r in relations}
        assert RelationType.DEPENDS_ON in rel_types or RelationType.USES in rel_types

    def test_directional_extraction_no_inverted_edges(self, sample_chunk):
        extractor = RelationExtractor(use_llm_if_available=False)
        relations = extractor.extract(sample_chunk)

        pairs = {(r.source_id, r.type, r.target_id) for r in relations}
        # Forward dependency must exist
        assert ("entity:acme_corp", RelationType.DEPENDS_ON, "entity:product_nova") in pairs
        # Inverted false dependency must NOT exist
        assert ("entity:product_nova", RelationType.DEPENDS_ON, "entity:acme_corp") not in pairs
        # Product Nova -> Identity Service must exist
        assert ("entity:product_nova", RelationType.DEPENDS_ON, "entity:identity_service") in pairs
        # Identity Service -> Product Nova must NOT exist
        assert ("entity:identity_service", RelationType.DEPENDS_ON, "entity:product_nova") not in pairs
        # Product Nova -> AWS must exist as DEPLOYS_TO
        assert ("entity:product_nova", RelationType.DEPLOYS_TO, "entity:aws") in pairs
        # AWS -> Product Nova must NOT exist
        assert ("entity:aws", RelationType.DEPLOYS_TO, "entity:product_nova") not in pairs


class TestEntityResolver:
    """Test suite for canonicalization, alias resolution, and edge re-mapping."""

    def test_alias_resolution(self):
        resolver = EntityResolver()

        e1 = Entity(id="temp:1", name="Nova", type=EntityType.PRODUCT)
        e2 = Entity(id="temp:2", name="Product Nova", type=EntityType.PRODUCT)
        e3 = Entity(id="temp:3", name="IdP", type=EntityType.SERVICE)
        e4 = Entity(id="temp:4", name="Identity Service", type=EntityType.SERVICE)

        canonicals = resolver.resolve_entities([e1, e2, e3, e4])
        canonical_names = {c.canonical_name for c in canonicals}

        assert "Product Nova" in canonical_names
        assert "Identity Service" in canonical_names
        assert len(canonicals) == 2  # Nova and Product Nova merged; IdP and Identity Service merged

        nova_canonical = next(c for c in canonicals if c.canonical_name == "Product Nova")
        assert nova_canonical.canonical_id == "entity:product:nova"
        assert "Nova" in nova_canonical.source_mentions or "Nova" in nova_canonical.aliases

    def test_relationship_remapping_and_evidence_merge(self, sample_chunk):
        entity_ext = EntityExtractor(use_llm_if_available=False)
        rel_ext = RelationExtractor(use_llm_if_available=False)
        resolver = EntityResolver()

        entities = entity_ext.extract(sample_chunk)
        relations = rel_ext.extract(sample_chunk, entities)
        canonical_entities = resolver.resolve_entities(entities)

        resolved_rels = resolver.resolve_relationships(relations, canonical_entities)
        assert len(resolved_rels) >= 1

        for r in resolved_rels:
            # Source and target IDs must start with entity:
            assert r.source_id.startswith("entity:")
            assert r.target_id.startswith("entity:")
            assert r.source_id != r.target_id

    def test_slug_and_hyphenated_remapping(self):
        resolver = EntityResolver()

        # Canonical entity with hyphenated name and 3-part ID
        ce = CanonicalEntity(
            canonical_id="entity:incident:inc_402",
            canonical_name="INC-402",
            primary_type=EntityType.INCIDENT,
            aliases=["Incident 402"],
        )

        # Raw relationship referencing slug ID entity:inc_402
        rel = Relationship(
            id="rel_temp",
            source_id="entity:customer:acme_corp",
            target_id="entity:inc_402",
            type=RelationType.AFFECTS,
            description="Acme was affected by INC-402",
            weight=1.0,
            evidence=[Evidence(chunk_id="c1", document_id="d1", text="Acme Corp affected by INC-402.")],
        )

        resolved = resolver.resolve_relationships([rel], [ce])
        assert len(resolved) == 1
        assert resolved[0].target_id == "entity:incident:inc_402"


class TestEndToEndKnowledgeExtraction:
    """Integration test loading enterprise documents, chunking, and extracting graph elements."""

    def test_pipeline_on_core_documents(self):
        loader = MarkdownLoader()
        chunker = SemanticChunker(chunk_size=500, chunk_overlap=100)
        entity_ext = EntityExtractor(use_llm_if_available=False)
        rel_ext = RelationExtractor(use_llm_if_available=False)
        resolver = EntityResolver()

        # Load 4 key multi-hop documents
        test_doc_names = ["customer_acme.md", "product_nova.md", "authentication.md", "incident_response.md"]
        docs = [loader.load_file(DOCUMENTS_DIR / name) for name in test_doc_names]
        chunks = chunker.chunk_documents(docs)

        raw_entities = entity_ext.extract_batch(chunks)
        raw_relations = rel_ext.extract_batch(chunks)

        canonical_entities = resolver.resolve_entities(raw_entities)
        resolved_relations = resolver.resolve_relationships(raw_relations, canonical_entities)

        # Validate extracted canonical entities
        c_names = {c.canonical_name for c in canonical_entities}
        assert "Acme Corp" in c_names
        assert "Product Nova" in c_names
        assert "Identity Service" in c_names
        assert "OAuth 2.1" in c_names
        assert "INC-402" in c_names

        # Validate multi-hop relations extracted
        rel_tuples = {(r.source_id, r.type.value, r.target_id) for r in resolved_relations}
        # Check that Nova -> Identity Service relationship exists
        nova_to_identity = any(
            "nova" in src and "identity_service" in tgt
            for src, r_type, tgt in rel_tuples
        )
        assert nova_to_identity, f"Expected Nova -> Identity Service relation not found in {rel_tuples}"
