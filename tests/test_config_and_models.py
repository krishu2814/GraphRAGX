"""Tests for configuration settings and foundational domain models."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models.entities import CanonicalEntity, Entity, EntityType
from app.models.query import LinkedEntity, QueryIntent, RetrievalPlan, RetrievalStrategy
from app.models.relationships import Evidence, Relationship, RelationType
from app.models.responses import Citation, ComparisonResult, QueryResponse
from app.models.retrieval import (
    CommunitySummary,
    FusionResult,
    GraphFact,
    RetrievalPath,
    RetrievedChunk,
)


class TestSettings:
    """Test suite for configuration loading and defaults."""

    def test_default_settings(self):
        settings = Settings()
        assert settings.use_in_memory_graph is True
        assert settings.use_in_memory_vector is True
        assert settings.default_retrieval_strategy == "hybrid"
        assert settings.top_k_chunks == 5
        assert settings.max_graph_hops == 2
        assert settings.rrf_k == 60
        assert settings.vector_weight == 0.5
        assert settings.graph_weight == 0.3
        assert settings.entity_weight == 0.2

    def test_get_settings_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestEntityModels:
    """Test suite for Entity and CanonicalEntity domain models."""

    def test_entity_creation_and_alias(self):
        entity = Entity(
            id="entity:product:nova",
            name="Product Nova",
            type=EntityType.PRODUCT,
            description="Enterprise cloud analytics platform",
        )
        assert entity.id == "entity:product:nova"
        assert entity.type == EntityType.PRODUCT
        assert entity.aliases == []

        entity.add_alias("Nova")
        entity.add_alias("Nova Analytics")
        # Duplicate should not be added
        entity.add_alias("Nova")
        # Same as name (case insensitive) should not be added
        entity.add_alias("product nova")

        assert entity.aliases == ["Nova", "Nova Analytics"]

    def test_canonical_entity(self):
        canonical = CanonicalEntity(
            canonical_id="entity:service:identity_service",
            canonical_name="Identity Service",
            primary_type=EntityType.SERVICE,
            description="Centralized OAuth authentication service",
            aliases=["Auth Service", "Identity Provider", "IdP"],
            source_mentions=["Identity Service", "Auth Service"],
        )
        assert len(canonical.aliases) == 3
        assert canonical.primary_type == EntityType.SERVICE


class TestRelationshipModels:
    """Test suite for Relationship and Evidence models."""

    def test_evidence_validation(self):
        evidence = Evidence(
            chunk_id="chunk_product_nova_01",
            document_id="product_nova.md",
            text="Product Nova relies on Identity Service for OAuth 2.1 authentication.",
            confidence=0.95,
        )
        assert evidence.confidence == 0.95

        with pytest.raises(ValidationError):
            Evidence(
                chunk_id="chunk_01",
                document_id="doc_01",
                text="Some text",
                confidence=1.5,  # Exceeds le=1.0
            )

    def test_relationship_evidence_deduplication(self):
        rel = Relationship(
            id="rel:nova:depends_on:identity_service",
            source_id="entity:product:nova",
            target_id="entity:service:identity_service",
            type=RelationType.DEPENDS_ON,
            description="Nova delegates authentication to Identity Service",
        )
        assert len(rel.evidence) == 0

        rel.add_evidence("chunk_01", "doc_nova.md", "Evidence sentence 1")
        rel.add_evidence("chunk_02", "doc_auth.md", "Evidence sentence 2")
        # Duplicate chunk ID should be ignored
        rel.add_evidence("chunk_01", "doc_nova.md", "Duplicate chunk ignored")

        assert len(rel.evidence) == 2
        assert rel.evidence[0].chunk_id == "chunk_01"
        assert rel.evidence[1].chunk_id == "chunk_02"


class TestRetrievalModels:
    """Test suite for retrieval domain structures."""

    def test_retrieval_path_cypher_rendering(self):
        path = RetrievalPath(
            entities=["Acme Corp", "Product Nova", "Identity Service", "OAuth 2.1"],
            relationships=["USES", "DEPENDS_ON", "INTRODUCED_IN"],
            length=3,
            score=0.92,
        )
        cypher_str = path.to_cypher_like()
        expected = "(Acme Corp)-[:USES]->(Product Nova)-[:DEPENDS_ON]->(Identity Service)-[:INTRODUCED_IN]->(OAuth 2.1)"
        assert cypher_str == expected

    def test_fusion_result(self):
        fusion = FusionResult(
            chunk_id="chunk_nova_01",
            document_id="product_nova.md",
            text="Nova platform details",
            vector_score=0.88,
            vector_rank=1,
            graph_score=0.75,
            graph_rank=2,
            entity_score=0.9,
            rrf_score=0.032,
            final_score=0.85,
        )
        assert fusion.chunk_id == "chunk_nova_01"
        assert fusion.vector_rank == 1
        assert fusion.graph_rank == 2

    def test_community_summary(self):
        comm = CommunitySummary(
            community_id="comm_security",
            name="Security & Identity",
            level=0,
            entities=["Identity Service", "OAuth 2.1", "Authz Service"],
            summary_text="Central cluster governing authentication and authorization protocols.",
        )
        assert comm.name == "Security & Identity"
        assert len(comm.entities) == 3


class TestQueryAndResponseModels:
    """Test suite for query analysis and response serialization."""

    def test_retrieval_plan(self):
        seed = LinkedEntity(
            raw_mention="Product Nova",
            canonical_id="entity:product:nova",
            canonical_name="Product Nova",
            entity_type=EntityType.PRODUCT,
            confidence=0.99,
        )
        plan = RetrievalPlan(
            query="Which customers use Product Nova and are affected by OAuth 2.1?",
            intent=QueryIntent.MULTI_HOP,
            strategy=RetrievalStrategy.HYBRID,
            seed_entities=[seed],
            max_hops=3,
            require_paths=True,
        )
        assert plan.intent == QueryIntent.MULTI_HOP
        assert plan.strategy == RetrievalStrategy.HYBRID
        assert plan.max_hops == 3
        assert len(plan.seed_entities) == 1

    def test_query_response_and_comparison(self):
        chunk = RetrievedChunk(
            chunk_id="chunk_01",
            document_id="doc_01.md",
            text="Evidence passage",
            score=0.9,
            rank=1,
        )
        citation = Citation(
            citation_id="[1]",
            chunk_id="chunk_01",
            document_id="doc_01.md",
            quote="Evidence passage",
        )
        fact = GraphFact(
            source_entity="entity:customer:acme",
            relation="USES",
            target_entity="entity:product:nova",
        )

        resp_v = QueryResponse(
            query="Test query",
            answer="Vector answer",
            strategy=RetrievalStrategy.VECTOR,
            citations=[citation],
            retrieved_chunks=[chunk],
            graph_facts=[],
        )
        resp_g = QueryResponse(
            query="Test query",
            answer="Graph answer",
            strategy=RetrievalStrategy.GRAPH,
            citations=[citation],
            retrieved_chunks=[],
            graph_facts=[fact],
        )
        resp_h = QueryResponse(
            query="Test query",
            answer="Hybrid answer",
            strategy=RetrievalStrategy.HYBRID,
            citations=[citation],
            retrieved_chunks=[chunk],
            graph_facts=[fact],
        )

        comparison = ComparisonResult(
            query="Test query",
            vector_response=resp_v,
            graph_response=resp_g,
            hybrid_response=resp_h,
            analysis="Hybrid combined vector chunk context with 2-hop relational path.",
        )
        assert comparison.vector_response.strategy == RetrievalStrategy.VECTOR
        assert comparison.graph_response.strategy == RetrievalStrategy.GRAPH
        assert comparison.hybrid_response.strategy == RetrievalStrategy.HYBRID
