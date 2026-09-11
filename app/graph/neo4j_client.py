"""Dual graph storage driver providing a unified interface over live Neo4j and in-memory NetworkX."""

from abc import ABC, abstractmethod
import json
import logging
from typing import Any
import networkx as nx

from app.config import get_settings
from app.graph.cypher_queries import (
    GET_CHUNK_BY_ID,
    GET_ENTITY_BY_ID,
    GET_ENTITY_BY_NAME,
    GET_GRAPH_STATS,
    GET_NEIGHBORS_1HOP,
    LINK_CHUNK_TO_DOCUMENT,
    LINK_CHUNK_TO_ENTITY,
    MERGE_CHUNK_NODE,
    MERGE_DOCUMENT_NODE,
    MERGE_ENTITY_NODE,
    build_merge_relationship_query,
)
from app.graph.schema import get_schema_initialization_queries
from app.models.entities import CanonicalEntity, Entity
from app.models.relationships import Relationship

logger = logging.getLogger(__name__)


class GraphClient(ABC):
    """Abstract protocol interface defining all graph operations across drivers."""

    @abstractmethod
    def initialize_schema(self) -> None:
        """Create constraints and indexes."""
        pass

    @abstractmethod
    def add_entity(self, entity: CanonicalEntity | Entity) -> None:
        """Idempotently insert or update an entity node."""
        pass

    @abstractmethod
    def add_document(self, doc_id: str, title: str, department: str, access_tier: str, version: str) -> None:
        """Idempotently insert a document node."""
        pass

    @abstractmethod
    def add_chunk(self, chunk_id: str, doc_id: str, text: str, section_title: str, section_path: str, index: int) -> None:
        """Idempotently insert a chunk node and link it to its parent document."""
        pass

    @abstractmethod
    def add_relationship(self, rel: Relationship) -> None:
        """Insert or update a directed relationship edge with evidence."""
        pass

    @abstractmethod
    def link_chunk_to_entity(self, chunk_id: str, entity_id: str) -> None:
        """Create a MENTIONS edge between a chunk and an entity."""
        pass

    @abstractmethod
    def get_entity(self, identifier: str) -> dict[str, Any] | None:
        """Fetch an entity node by its ID or exact/alias name."""
        pass

    @abstractmethod
    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Fetch a chunk node by its ID."""
        pass

    @abstractmethod
    def get_neighbors(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve 1-hop neighbor relationships connected to an entity."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, int]:
        """Return total counts of entities, documents, chunks, and relationships."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Purge all nodes and edges from the graph."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection pools or release memory."""
        pass


class NetworkXGraphDriver(GraphClient):
    """In-memory graph driver conforming to GraphClient protocol using NetworkX MultiDiGraph."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.entity_lookup: dict[str, str] = {}  # maps lowercase names/aliases to entity_id

    def initialize_schema(self) -> None:
        """No-op for in-memory graph driver."""
        pass

    def add_entity(self, entity: CanonicalEntity | Entity) -> None:
        ent_id = entity.canonical_id if isinstance(entity, CanonicalEntity) else entity.id
        name = entity.canonical_name if isinstance(entity, CanonicalEntity) else entity.name
        ent_type = entity.primary_type.value if isinstance(entity, CanonicalEntity) else entity.type.value
        aliases = entity.aliases

        self.graph.add_node(
            ent_id,
            label="Entity",
            id=ent_id,
            name=name,
            type=ent_type,
            description=entity.description,
            aliases=aliases,
        )

        # Index for name/alias lookups
        self.entity_lookup[name.lower()] = ent_id
        for alias in aliases:
            self.entity_lookup[alias.lower()] = ent_id

    def add_document(self, doc_id: str, title: str, department: str, access_tier: str, version: str) -> None:
        self.graph.add_node(
            doc_id,
            label="Document",
            id=doc_id,
            title=title,
            department=department,
            access_tier=access_tier,
            version=version,
        )

    def add_chunk(self, chunk_id: str, doc_id: str, text: str, section_title: str, section_path: str, index: int) -> None:
        self.graph.add_node(
            chunk_id,
            label="Chunk",
            id=chunk_id,
            document_id=doc_id,
            text=text,
            section_title=section_title,
            section_path=section_path,
            index=index,
        )
        # Link to document
        if doc_id in self.graph:
            self.graph.add_edge(chunk_id, doc_id, key="PART_OF", relation="PART_OF")

    def add_relationship(self, rel: Relationship) -> None:
        evidence_dicts = [e.model_dump() for e in rel.evidence]

        # Ensure endpoints exist
        if rel.source_id not in self.graph:
            name = rel.source_id.split(":")[-1].replace("_", " ").title()
            self.graph.add_node(rel.source_id, label="Entity", id=rel.source_id, name=name, type="OTHER")
            self.entity_lookup[name.lower()] = rel.source_id
        if rel.target_id not in self.graph:
            name = rel.target_id.split(":")[-1].replace("_", " ").title()
            self.graph.add_node(rel.target_id, label="Entity", id=rel.target_id, name=name, type="OTHER")
            self.entity_lookup[name.lower()] = rel.target_id

        rel_type_str = rel.type.value

        # Check if edge already exists to merge evidence
        edge_data = None
        if self.graph.has_edge(rel.source_id, rel.target_id, key=rel_type_str):
            edge_data = self.graph.get_edge_data(rel.source_id, rel.target_id, key=rel_type_str)
            existing_evidence = edge_data.get("evidence", [])
            for ev in evidence_dicts:
                if not any(e.get("chunk_id") == ev.get("chunk_id") for e in existing_evidence):
                    existing_evidence.append(ev)
            edge_data["evidence"] = existing_evidence
            edge_data["weight"] += rel.weight
        else:
            self.graph.add_edge(
                rel.source_id,
                rel.target_id,
                key=rel_type_str,
                relation=rel_type_str,
                description=rel.description,
                weight=rel.weight,
                evidence=evidence_dicts,
            )

    def link_chunk_to_entity(self, chunk_id: str, entity_id: str) -> None:
        if chunk_id in self.graph and entity_id in self.graph:
            self.graph.add_edge(chunk_id, entity_id, key="MENTIONS", relation="MENTIONS")

    def get_entity(self, identifier: str) -> dict[str, Any] | None:
        # Check by direct ID
        if identifier in self.graph and self.graph.nodes[identifier].get("label") == "Entity":
            return dict(self.graph.nodes[identifier])

        # Check by name/alias lookup
        lookup_id = self.entity_lookup.get(identifier.lower())
        if lookup_id and lookup_id in self.graph:
            return dict(self.graph.nodes[lookup_id])

        return None

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        if chunk_id in self.graph and self.graph.nodes[chunk_id].get("label") == "Chunk":
            return dict(self.graph.nodes[chunk_id])
        return None

    def get_neighbors(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        # Resolve identifier if name passed
        ent = self.get_entity(entity_id)
        if not ent:
            return []
        resolved_id = ent["id"]

        neighbors: list[dict[str, Any]] = []

        # Outgoing edges
        for _, tgt, key, data in self.graph.out_edges(resolved_id, keys=True, data=True):
            if data.get("relation") in ["PART_OF", "MENTIONS"]:
                continue
            tgt_node = self.graph.nodes.get(tgt, {})
            neighbors.append({
                "source_id": resolved_id,
                "source_name": ent.get("name") or resolved_id,
                "relation": data.get("relation", key),
                "description": data.get("description", ""),
                "evidence": data.get("evidence", []),
                "target_id": tgt,
                "target_name": tgt_node.get("name") or tgt,
                "target_type": tgt_node.get("type", "OTHER"),
                "direction": "OUTGOING",
            })

        # Incoming edges
        for src, _, key, data in self.graph.in_edges(resolved_id, keys=True, data=True):
            if data.get("relation") in ["PART_OF", "MENTIONS"]:
                continue
            src_node = self.graph.nodes.get(src, {})
            neighbors.append({
                "source_id": src,
                "source_name": src_node.get("name") or src,
                "relation": data.get("relation", key),
                "description": data.get("description", ""),
                "evidence": data.get("evidence", []),
                "target_id": resolved_id,
                "target_name": ent.get("name") or resolved_id,
                "target_type": ent.get("type", "OTHER"),
                "direction": "INCOMING",
            })

        return neighbors[:limit]

    def get_stats(self) -> dict[str, int]:
        entities = sum(1 for _, d in self.graph.nodes(data=True) if d.get("label") == "Entity")
        documents = sum(1 for _, d in self.graph.nodes(data=True) if d.get("label") == "Document")
        chunks = sum(1 for _, d in self.graph.nodes(data=True) if d.get("label") == "Chunk")
        relationships = sum(
            1 for _, _, d in self.graph.edges(data=True)
            if d.get("relation") not in ["PART_OF", "MENTIONS"]
        )
        return {
            "entity_count": entities,
            "document_count": documents,
            "chunk_count": chunks,
            "relationship_count": relationships,
        }

    def clear(self) -> None:
        self.graph.clear()
        self.entity_lookup.clear()

    def close(self) -> None:
        self.clear()


class Neo4jGraphDriver(GraphClient):
    """Production graph driver connecting to Neo4j via official neo4j Bolt driver."""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def initialize_schema(self) -> None:
        queries = get_schema_initialization_queries()
        with self.driver.session(database=self.database) as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    logger.debug(f"Schema query executed with notice: {e}")

    def add_entity(self, entity: CanonicalEntity | Entity) -> None:
        ent_id = entity.canonical_id if isinstance(entity, CanonicalEntity) else entity.id
        name = entity.canonical_name if isinstance(entity, CanonicalEntity) else entity.name
        ent_type = entity.primary_type.value if isinstance(entity, CanonicalEntity) else entity.type.value
        aliases = entity.aliases

        with self.driver.session(database=self.database) as session:
            session.run(
                MERGE_ENTITY_NODE,
                id=ent_id,
                name=name,
                type=ent_type,
                description=entity.description,
                aliases=aliases,
            )

    def add_document(self, doc_id: str, title: str, department: str, access_tier: str, version: str) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                MERGE_DOCUMENT_NODE,
                id=doc_id,
                title=title,
                department=department,
                access_tier=access_tier,
                version=version,
            )

    def add_chunk(self, chunk_id: str, doc_id: str, text: str, section_title: str, section_path: str, index: int) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                MERGE_CHUNK_NODE,
                id=chunk_id,
                document_id=doc_id,
                text=text,
                section_title=section_title,
                section_path=section_path,
                index=index,
            )
            session.run(LINK_CHUNK_TO_DOCUMENT, chunk_id=chunk_id, document_id=doc_id)

    def add_relationship(self, rel: Relationship) -> None:
        evidence_json = json.dumps([e.model_dump() for e in rel.evidence])
        query = build_merge_relationship_query(rel.type.value)

        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                source_id=rel.source_id,
                target_id=rel.target_id,
                description=rel.description,
                weight=rel.weight,
                evidence=evidence_json,
            )

    def link_chunk_to_entity(self, chunk_id: str, entity_id: str) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(LINK_CHUNK_TO_ENTITY, chunk_id=chunk_id, entity_id=entity_id)

    def get_entity(self, identifier: str) -> dict[str, Any] | None:
        with self.driver.session(database=self.database) as session:
            res = session.run(GET_ENTITY_BY_ID, id=identifier)
            record = res.single()
            if record:
                return dict(record)

            res_name = session.run(GET_ENTITY_BY_NAME, name=identifier)
            record_name = res_name.single()
            if record_name:
                return dict(record_name)
        return None

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self.driver.session(database=self.database) as session:
            res = session.run(GET_CHUNK_BY_ID, id=chunk_id)
            record = res.single()
            if record:
                return dict(record)
        return None

    def get_neighbors(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            res = session.run(GET_NEIGHBORS_1HOP, id=entity_id, limit=limit)
            results: list[dict[str, Any]] = []
            for r in res:
                item = dict(r)
                ev = item.get("evidence")
                if isinstance(ev, str):
                    try:
                        item["evidence"] = json.loads(ev)
                    except Exception:
                        item["evidence"] = []
                elif not isinstance(ev, list):
                    item["evidence"] = []
                results.append(item)
            return results

    def get_stats(self) -> dict[str, int]:
        with self.driver.session(database=self.database) as session:
            res = session.run(GET_GRAPH_STATS)
            record = res.single()
            if record:
                return {
                    "entity_count": record["entity_count"],
                    "document_count": record["document_count"],
                    "chunk_count": record["chunk_count"],
                    "relationship_count": record["relationship_count"],
                }
        return {"entity_count": 0, "document_count": 0, "chunk_count": 0, "relationship_count": 0}

    def clear(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        self.driver.close()


def get_graph_client(force_in_memory: bool = False) -> GraphClient:
    """Factory creating configured GraphClient (Neo4j or NetworkX in-memory fallback)."""
    settings = get_settings()

    if force_in_memory or settings.use_in_memory_graph:
        return NetworkXGraphDriver()

    try:
        driver = Neo4jGraphDriver(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
        # Test connectivity with ping query
        driver.get_stats()
        return driver
    except Exception as e:
        logger.warning(
            f"Unable to connect to Neo4j at {settings.neo4j_uri} ({e}). "
            f"Activating seamless in-memory NetworkX graph driver fallback."
        )
        return NetworkXGraphDriver()
