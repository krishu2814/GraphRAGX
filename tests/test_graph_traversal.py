"""Unit and integration tests for graph traversal and multi-hop path retrieval."""

import pytest

from app.graph.neo4j_client import NetworkXGraphDriver
from app.graph.traversal import GraphTraverser
from app.ingestion.pipeline import IngestionPipeline
from app.models.entities import CanonicalEntity, EntityType
from app.models.relationships import Evidence, Relationship, RelationType
from app.models.retrieval import MultiHopResult, RetrievalPath
from app.retrieval.multi_hop_retriever import MultiHopRetriever


@pytest.fixture
def synthetic_graph() -> NetworkXGraphDriver:
    """Create a small predictable synthetic knowledge graph with chunks and relationships."""
    driver = NetworkXGraphDriver()

    # Add entities
    e1 = CanonicalEntity(
        canonical_id="ent_company_acme",
        canonical_name="Acme Corp",
        primary_type=EntityType.ORGANIZATION,
        aliases=["Acme"],
        description="Global retail corporation",
    )
    e2 = CanonicalEntity(
        canonical_id="ent_prod_nova",
        canonical_name="Product Nova",
        primary_type=EntityType.PRODUCT,
        aliases=["Nova"],
        description="Flagship analytics engine",
    )
    e3 = CanonicalEntity(
        canonical_id="ent_svc_identity",
        canonical_name="Identity Service",
        primary_type=EntityType.SERVICE,
        aliases=["Auth Service"],
        description="Central authentication microservice",
    )
    e4 = CanonicalEntity(
        canonical_id="ent_proto_oauth",
        canonical_name="OAuth 2.1",
        primary_type=EntityType.TECHNOLOGY,
        aliases=["OAuth"],
        description="Authorization protocol standard",
    )

    for e in [e1, e2, e3, e4]:
        driver.add_entity(e)

    # Add document and chunks
    driver.add_document("doc_01", "Architecture Guide", "Engineering", "Internal", "v1.0")
    driver.add_chunk(
        chunk_id="chunk_01",
        doc_id="doc_01",
        text="Acme Corp uses Product Nova for core analytics.",
        section_title="Usage",
        section_path="Usage > Nova",
        index=0,
    )
    driver.add_chunk(
        chunk_id="chunk_02",
        doc_id="doc_01",
        text="Product Nova depends on Identity Service for user tokens.",
        section_title="Architecture",
        section_path="Architecture > Auth",
        index=1,
    )
    driver.add_chunk(
        chunk_id="chunk_03",
        doc_id="doc_01",
        text="Identity Service implements OAuth 2.1 with PKCE.",
        section_title="Security",
        section_path="Security > Protocols",
        index=2,
    )

    # Add relationships:
    # Acme Corp -USES-> Product Nova
    driver.add_relationship(
        Relationship(
            id="rel_acme_nova",
            source_id="ent_company_acme",
            target_id="ent_prod_nova",
            type=RelationType.USES,
            description="Acme uses Nova",
            weight=1.0,
            evidence=[Evidence(chunk_id="chunk_01", document_id="doc_01", text="Acme Corp uses Product Nova.")],
        )
    )

    # Product Nova -DEPENDS_ON-> Identity Service
    driver.add_relationship(
        Relationship(
            id="rel_nova_identity",
            source_id="ent_prod_nova",
            target_id="ent_svc_identity",
            type=RelationType.DEPENDS_ON,
            description="Nova depends on Identity Service",
            weight=1.0,
            evidence=[Evidence(chunk_id="chunk_02", document_id="doc_01", text="Product Nova depends on Identity Service.")],
        )
    )

    # Identity Service -INTEGRATES_WITH-> OAuth 2.1
    driver.add_relationship(
        Relationship(
            id="rel_identity_oauth",
            source_id="ent_svc_identity",
            target_id="ent_proto_oauth",
            type=RelationType.INTEGRATES_WITH,
            description="Identity Service integrates with OAuth 2.1",
            weight=1.0,
            evidence=[Evidence(chunk_id="chunk_03", document_id="doc_01", text="Identity Service implements OAuth 2.1.")],
        )
    )

    # Add cycle edge: OAuth 2.1 -RELATED_TO-> Acme Corp to test cycle prevention
    driver.add_relationship(
        Relationship(
            id="rel_oauth_acme",
            source_id="ent_proto_oauth",
            target_id="ent_company_acme",
            type=RelationType.RELATED_TO,
            description="Acme security standard compliance",
            weight=1.0,
            evidence=[Evidence(chunk_id="chunk_03", document_id="doc_01", text="Acme follows standards.")],
        )
    )

    return driver


class TestGraphTraverser:
    """Tests for BFS graph traversal, path scoring, cycle prevention, and fact discovery."""

    def test_single_hop_path_discovery(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        paths = traverser.find_paths("Acme Corp", max_hops=1)

        assert len(paths) == 1
        path = paths[0]
        assert path.entities == ["Acme Corp", "Product Nova"]
        assert path.relationships == ["USES"]
        assert path.length == 1
        assert path.score == 1.0
        assert "chunk_01" in path.evidence_chunk_ids
        assert path.to_cypher_like() == "(Acme Corp)-[:USES]->(Product Nova)"

    def test_multi_hop_path_discovery(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        paths = traverser.find_paths("Acme Corp", max_hops=2)

        # Should discover 1-hop path and 2-hop path
        assert len(paths) == 2
        p1 = paths[0]
        assert p1.length == 1
        assert p1.entities == ["Acme Corp", "Product Nova"]

        p2 = paths[1]
        assert p2.length == 2
        assert p2.entities == ["Acme Corp", "Product Nova", "Identity Service"]
        assert p2.relationships == ["USES", "DEPENDS_ON"]
        assert p2.score < p1.score  # Longer paths have attenuated scores
        assert "chunk_01" in p2.evidence_chunk_ids
        assert "chunk_02" in p2.evidence_chunk_ids
        assert p2.to_cypher_like() == "(Acme Corp)-[:USES]->(Product Nova)-[:DEPENDS_ON]->(Identity Service)"

    def test_three_hop_path_discovery(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        paths = traverser.find_paths("Acme Corp", max_hops=3)

        assert len(paths) == 3
        p3 = paths[2]
        assert p3.length == 3
        assert p3.entities == ["Acme Corp", "Product Nova", "Identity Service", "OAuth 2.1"]
        assert p3.relationships == ["USES", "DEPENDS_ON", "INTEGRATES_WITH"]
        assert "chunk_03" in p3.evidence_chunk_ids

    def test_cycle_prevention(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        # We set max_hops=5 with a cycle (Acme -> Nova -> Identity -> OAuth -> Acme)
        paths = traverser.find_paths("Acme Corp", max_hops=5)

        # Traversal must terminate cleanly without looping back onto Acme Corp
        for p in paths:
            # No entity should be repeated in the path
            assert len(p.entities) == len(set(p.entities))

    def test_unknown_entity_returns_empty_paths(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        paths = traverser.find_paths("NonExistentCorp", max_hops=2)
        assert paths == []

    def test_fact_extraction(self, synthetic_graph: NetworkXGraphDriver) -> None:
        traverser = GraphTraverser(synthetic_graph)
        facts = traverser.find_facts("Acme Corp", max_hops=2)

        assert len(facts) >= 2
        # Check first fact
        f1 = facts[0]
        assert f1.source_name == "Acme Corp"
        assert f1.relation == "USES"
        assert f1.target_name == "Product Nova"

        # Check second fact
        f2 = facts[1]
        assert f2.source_name == "Product Nova"
        assert f2.relation == "DEPENDS_ON"
        assert f2.target_name == "Identity Service"


class TestMultiHopRetriever:
    """Tests for MultiHopRetriever returning paths, facts, and grounded evidence chunks."""

    def test_retrieve_with_grounded_chunks(self, synthetic_graph: NetworkXGraphDriver) -> None:
        retriever = MultiHopRetriever(client=synthetic_graph)
        result = retriever.retrieve("Acme Corp", max_hops=2)

        assert isinstance(result, MultiHopResult)
        assert result.seed_entity == "Acme Corp"
        assert len(result.paths) == 2
        assert len(result.facts) == 2

        # Evidence chunks must be retrieved with actual text from the graph
        assert len(result.evidence_chunks) == 2
        chunk_ids = [c.chunk_id for c in result.evidence_chunks]
        assert "chunk_01" in chunk_ids
        assert "chunk_02" in chunk_ids

        # Check chunk content
        c1 = next(c for c in result.evidence_chunks if c.chunk_id == "chunk_01")
        assert "Acme Corp uses Product Nova" in c1.text
        assert c1.document_id == "doc_01"

    def test_empty_query_returns_empty_result(self, synthetic_graph: NetworkXGraphDriver) -> None:
        retriever = MultiHopRetriever(client=synthetic_graph)
        result = retriever.retrieve("   ")
        assert result.paths == []
        assert result.facts == []
        assert result.evidence_chunks == []


@pytest.fixture(scope="module")
def corpus_graph() -> NetworkXGraphDriver:
    driver = NetworkXGraphDriver()
    pipeline = IngestionPipeline(
        data_dir="data/documents",
        client=driver,
        index_vectors=False,
    )
    pipeline.run()
    return driver


class TestCorpusTraversalIntegration:
    """End-to-end traversal integration tests across the 20-document corpus."""

    def test_acme_multi_hop_traversal_on_corpus(self, corpus_graph: NetworkXGraphDriver) -> None:
        retriever = MultiHopRetriever(client=corpus_graph)
        result = retriever.retrieve("Acme Corp", max_hops=2, max_paths=10)

        assert len(result.paths) > 0
        assert len(result.facts) > 0
        assert len(result.evidence_chunks) > 0

        # Verify evidence chunk texts are populated
        for chunk in result.evidence_chunks:
            assert chunk.chunk_id.startswith("chunk_")
            assert len(chunk.text) > 0
            assert chunk.document_id != ""

    def test_product_nova_multi_hop_traversal(self, corpus_graph: NetworkXGraphDriver) -> None:
        retriever = MultiHopRetriever(client=corpus_graph)
        result = retriever.retrieve("Product Nova", max_hops=2, max_paths=10)

        assert len(result.paths) > 0
        # Target entities should include key related components
        target_entities = [p.entities[-1] for p in result.paths]
        assert any("Engine" in t or "Product" in t or "Service" in t for t in target_entities)
