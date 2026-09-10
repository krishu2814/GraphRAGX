"""Unit tests for dual graph storage engine (schema, Cypher catalog, NetworkX driver, and factory)."""

import pytest

from app.graph.cypher_queries import build_merge_relationship_query
from app.graph.neo4j_client import (
    GraphClient,
    NetworkXGraphDriver,
    get_graph_client,
)
from app.graph.schema import CONSTRAINTS, INDEXES, get_schema_initialization_queries
from app.models.entities import CanonicalEntity, EntityType
from app.models.relationships import Evidence, Relationship, RelationType


class TestGraphSchema:
    """Test suite for graph schema definitions, constraints, and indexes."""

    def test_schema_queries_generation(self):
        queries = get_schema_initialization_queries()
        assert len(queries) == len(CONSTRAINTS) + len(INDEXES)

        # Check critical uniqueness constraints
        combined_text = " ".join(queries)
        assert "e.id IS UNIQUE" in combined_text
        assert "d.id IS UNIQUE" in combined_text
        assert "c.id IS UNIQUE" in combined_text
        assert "e.name" in combined_text

    def test_cypher_relationship_builder(self):
        query = build_merge_relationship_query("DEPENDS_ON")
        assert "MATCH (s:Entity {id: $source_id})" in query
        assert "MATCH (t:Entity {id: $target_id})" in query
        assert "MERGE (s)-[r:DEPENDS_ON]->(t)" in query
        assert "r.evidence = $evidence" in query


class TestNetworkXGraphDriver:
    """Test suite validating in-memory GraphClient implementation using NetworkX."""

    @pytest.fixture
    def driver(self):
        client = NetworkXGraphDriver()
        yield client
        client.close()

    def test_add_and_retrieve_entity(self, driver: NetworkXGraphDriver):
        entity = CanonicalEntity(
            canonical_id="entity:product:nova",
            canonical_name="Product Nova",
            primary_type=EntityType.PRODUCT,
            description="Enterprise cloud analytics platform",
            aliases=["Nova", "Nova Analytics"],
        )
        driver.add_entity(entity)

        # Retrieve by canonical ID
        res_by_id = driver.get_entity("entity:product:nova")
        assert res_by_id is not None
        assert res_by_id["name"] == "Product Nova"
        assert res_by_id["type"] == "PRODUCT"

        # Retrieve by primary name
        res_by_name = driver.get_entity("Product Nova")
        assert res_by_name is not None
        assert res_by_name["id"] == "entity:product:nova"

        # Retrieve by alias
        res_by_alias = driver.get_entity("nova")
        assert res_by_alias is not None
        assert res_by_alias["id"] == "entity:product:nova"

    def test_document_and_chunk_linking(self, driver: NetworkXGraphDriver):
        driver.add_document(
            doc_id="doc_nova",
            title="Product Nova Overview",
            department="Engineering",
            access_tier="Internal",
            version="3.2",
        )
        driver.add_chunk(
            chunk_id="chunk_nova_001",
            doc_id="doc_nova",
            text="Nova is an analytics engine.",
            section_title="Overview",
            section_path="Product Nova Overview > Overview",
            index=1,
        )

        stats = driver.get_stats()
        assert stats["document_count"] == 1
        assert stats["chunk_count"] == 1

        # Check PART_OF edge exists in graph
        assert driver.graph.has_edge("chunk_nova_001", "doc_nova", key="PART_OF")

    def test_add_relationship_with_evidence_and_deduplication(self, driver: NetworkXGraphDriver):
        e1 = CanonicalEntity(
            canonical_id="entity:product:nova",
            canonical_name="Product Nova",
            primary_type=EntityType.PRODUCT,
        )
        e2 = CanonicalEntity(
            canonical_id="entity:service:identity_service",
            canonical_name="Identity Service",
            primary_type=EntityType.SERVICE,
        )
        driver.add_entity(e1)
        driver.add_entity(e2)

        evidence1 = Evidence(
            chunk_id="chunk_nova_001",
            document_id="product_nova.md",
            text="Nova relies on Identity Service.",
            confidence=0.95,
        )
        rel1 = Relationship(
            id="rel:nova:depends_on:identity",
            source_id="entity:product:nova",
            target_id="entity:service:identity_service",
            type=RelationType.DEPENDS_ON,
            description="Nova delegates authentication",
            evidence=[evidence1],
        )
        driver.add_relationship(rel1)

        # Add duplicate relationship from second chunk
        evidence2 = Evidence(
            chunk_id="chunk_auth_002",
            document_id="authentication.md",
            text="Identity Service authenticates Nova users.",
            confidence=0.90,
        )
        rel2 = Relationship(
            id="rel:nova:depends_on:identity",
            source_id="entity:product:nova",
            target_id="entity:service:identity_service",
            type=RelationType.DEPENDS_ON,
            description="Nova delegates authentication",
            evidence=[evidence2],
        )
        driver.add_relationship(rel2)

        stats = driver.get_stats()
        assert stats["relationship_count"] == 1

        # Check evidence was merged
        edge_data = driver.graph.get_edge_data("entity:product:nova", "entity:service:identity_service", key="DEPENDS_ON")
        assert len(edge_data["evidence"]) == 2
        chunk_ids = {e["chunk_id"] for e in edge_data["evidence"]}
        assert "chunk_nova_001" in chunk_ids
        assert "chunk_auth_002" in chunk_ids

    def test_get_neighbors(self, driver: NetworkXGraphDriver):
        driver.add_entity(CanonicalEntity(canonical_id="entity:a", canonical_name="Node A", primary_type=EntityType.PRODUCT))
        driver.add_entity(CanonicalEntity(canonical_id="entity:b", canonical_name="Node B", primary_type=EntityType.SERVICE))
        driver.add_entity(CanonicalEntity(canonical_id="entity:c", canonical_name="Node C", primary_type=EntityType.CUSTOMER))

        driver.add_relationship(Relationship(
            id="r1", source_id="entity:a", target_id="entity:b", type=RelationType.DEPENDS_ON,
        ))
        driver.add_relationship(Relationship(
            id="r2", source_id="entity:c", target_id="entity:a", type=RelationType.USES,
        ))

        neighbors = driver.get_neighbors("entity:a")
        assert len(neighbors) == 2

        directions = {n["direction"] for n in neighbors}
        assert "OUTGOING" in directions  # a -> b
        assert "INCOMING" in directions  # c -> a

    def test_clear_graph(self, driver: NetworkXGraphDriver):
        driver.add_entity(CanonicalEntity(canonical_id="entity:a", canonical_name="Node A", primary_type=EntityType.PRODUCT))
        assert driver.get_stats()["entity_count"] == 1

        driver.clear()
        assert driver.get_stats()["entity_count"] == 0
        assert driver.get_entity("entity:a") is None


class TestGraphClientFactory:
    """Test suite validating client factory and fallback."""

    def test_force_in_memory_returns_networkx(self):
        client = get_graph_client(force_in_memory=True)
        assert isinstance(client, NetworkXGraphDriver)

    def test_default_config_returns_networkx_without_running_neo4j(self):
        # Settings default has use_in_memory_graph=True
        client = get_graph_client()
        assert isinstance(client, NetworkXGraphDriver)
