"""Unit and integration tests for GraphBuilder and IngestionPipeline."""

from pathlib import Path
import pytest

from app.graph.neo4j_client import NetworkXGraphDriver
from app.ingestion.chunker import DocumentChunk, SemanticChunker
from app.ingestion.graph_builder import GraphBuilder
from app.ingestion.loaders import LoadedDocument, MarkdownLoader
from app.ingestion.metadata import AccessTier, ChunkMetadata
from app.ingestion.pipeline import IngestionPipeline, IngestionSummary
from app.models.entities import CanonicalEntity, EntityType
from app.models.relationships import Evidence, Relationship, RelationType

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"


class TestGraphBuilder:
    """Test suite for GraphBuilder node/edge insertion and idempotency."""

    @pytest.fixture
    def client(self):
        driver = NetworkXGraphDriver()
        yield driver
        driver.close()

    def test_idempotent_population(self, client: NetworkXGraphDriver):
        builder = GraphBuilder(client)

        meta = ChunkMetadata(
            document_id="doc_test",
            title="Test Doc",
            department="Engineering",
            access_tier=AccessTier.INTERNAL,
            version="1.0",
        )
        chunk = DocumentChunk(
            chunk_id="chunk_test_001",
            document_id="doc_test",
            text="Acme Corp uses Product Nova.",
            index=1,
            metadata=meta,
        )
        entity1 = CanonicalEntity(
            canonical_id="entity:customer:acme",
            canonical_name="Acme Corp",
            primary_type=EntityType.CUSTOMER,
        )
        entity2 = CanonicalEntity(
            canonical_id="entity:product:nova",
            canonical_name="Product Nova",
            primary_type=EntityType.PRODUCT,
        )
        rel = Relationship(
            id="rel:acme:uses:nova",
            source_id="entity:customer:acme",
            target_id="entity:product:nova",
            type=RelationType.USES,
            description="Acme uses Nova",
            evidence=[Evidence(chunk_id="chunk_test_001", document_id="doc_test", text="Acme Corp uses Product Nova.")],
        )

        # First population
        stats1 = builder.populate(
            chunks=[chunk],
            entities=[entity1, entity2],
            relationships=[rel],
        )
        assert stats1["document_count"] == 1
        assert stats1["chunk_count"] == 1
        assert stats1["entity_count"] == 2
        assert stats1["relationship_count"] == 1

        # Second population (Idempotency check)
        stats2 = builder.populate(
            chunks=[chunk],
            entities=[entity1, entity2],
            relationships=[rel],
        )
        assert stats2["document_count"] == 1
        assert stats2["chunk_count"] == 1
        assert stats2["entity_count"] == 2
        assert stats2["relationship_count"] == 1

        # Check structural MENTIONS link
        assert client.graph.has_edge("chunk_test_001", "entity:customer:acme", key="MENTIONS")
        assert client.graph.has_edge("chunk_test_001", "entity:product:nova", key="MENTIONS")

    def test_mentions_linking_word_boundaries(self, client: NetworkXGraphDriver):
        builder = GraphBuilder(client)
        meta = ChunkMetadata(
            document_id="doc_boundary_test",
            title="Boundary Test",
            department="Engineering",
            access_tier=AccessTier.INTERNAL,
            version="1.0",
        )
        chunk = DocumentChunk(
            chunk_id="chunk_boundary_001",
            document_id="doc_boundary_test",
            text="We completed the office renovation and improved our build process.",
            index=1,
            metadata=meta,
        )
        entity_nova = CanonicalEntity(
            canonical_id="entity:product:nova",
            canonical_name="Product Nova",
            primary_type=EntityType.PRODUCT,
            aliases=["Nova"],
        )
        entity_pro = CanonicalEntity(
            canonical_id="entity:plan:pro",
            canonical_name="Pro Tier",
            primary_type=EntityType.PLAN,
            aliases=["Pro"],
        )

        builder.populate(
            chunks=[chunk],
            entities=[entity_nova, entity_pro],
            relationships=[],
        )

        # Neither 'Nova' (in renovation) nor 'Pro' (in process) should be linked
        assert not client.graph.has_edge("chunk_boundary_001", "entity:product:nova", key="MENTIONS")
        assert not client.graph.has_edge("chunk_boundary_001", "entity:plan:pro", key="MENTIONS")


class TestIngestionPipeline:
    """Integration test suite executing full pipeline on the enterprise documents corpus."""

    def test_full_corpus_ingestion(self):
        client = NetworkXGraphDriver()
        pipeline = IngestionPipeline(data_dir=DOCUMENTS_DIR, use_llm=False, client=client)

        summary: IngestionSummary = pipeline.run()

        # Validate summary metrics
        assert summary.documents_loaded == 20
        assert summary.chunks_created >= 40
        assert summary.canonical_entities_count >= 25
        assert summary.resolved_relationships_count >= 50
        assert summary.duration_ms > 0

        # Validate that client graph store reflects populated data
        stats = client.get_stats()
        assert stats["document_count"] == 20
        assert stats["chunk_count"] == summary.chunks_created
        assert stats["entity_count"] >= summary.canonical_entities_count
        assert stats["relationship_count"] == summary.resolved_relationships_count

        # Check that core entities exist in graph
        nova_node = client.get_entity("Product Nova")
        assert nova_node is not None
        assert nova_node["type"] == "PRODUCT"

        identity_node = client.get_entity("Identity Service")
        assert identity_node is not None
        assert identity_node["type"] == "SERVICE"

        acme_node = client.get_entity("Acme Corp")
        assert acme_node is not None
        assert acme_node["type"] == "CUSTOMER"

        # Check that 1-hop neighbor queries return valid relations
        nova_neighbors = client.get_neighbors("Product Nova")
        assert len(nova_neighbors) >= 2

        client.close()
