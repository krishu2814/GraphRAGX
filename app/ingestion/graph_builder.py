"""Graph builder module responsible for idempotent population of nodes and relationships into the graph store."""

import logging
from typing import Any

from app.graph.neo4j_client import GraphClient
from app.ingestion.chunker import DocumentChunk
from app.ingestion.loaders import LoadedDocument
from app.models.entities import CanonicalEntity
from app.models.relationships import Relationship

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Populates graph databases idempotently with documents, chunks, entities, and relationships."""

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def populate(
        self,
        chunks: list[DocumentChunk],
        entities: list[CanonicalEntity],
        relationships: list[Relationship],
        documents: list[LoadedDocument] | None = None,
    ) -> dict[str, int]:
        """Idempotently insert all nodes, structural edges, and relational facts into the graph."""
        logger.info("Initializing graph schema constraints and indexes...")
        self.client.initialize_schema()

        # 1. Insert Document nodes
        doc_map: dict[str, LoadedDocument] = {}
        if documents:
            for doc in documents:
                doc_map[doc.document_id] = doc
                self.client.add_document(
                    doc_id=doc.document_id,
                    title=doc.title,
                    department=doc.department,
                    access_tier=doc.access_tier,
                    version=doc.version,
                )
        else:
            # Infer document nodes from chunk metadata if not provided explicitly
            seen_docs: set[str] = set()
            for chunk in chunks:
                if chunk.document_id not in seen_docs:
                    seen_docs.add(chunk.document_id)
                    self.client.add_document(
                        doc_id=chunk.document_id,
                        title=chunk.metadata.title,
                        department=chunk.metadata.department,
                        access_tier=chunk.metadata.access_tier.value,
                        version=chunk.metadata.version,
                    )

        # 2. Insert Chunk nodes & link (Chunk)-[:PART_OF]->(Document)
        logger.info(f"Inserting {len(chunks)} chunk nodes and PART_OF relationships...")
        for chunk in chunks:
            self.client.add_chunk(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.document_id,
                text=chunk.text,
                section_title=chunk.metadata.section_title,
                section_path=chunk.metadata.section_path,
                index=chunk.index,
            )

        # 3. Insert Canonical Entity nodes
        logger.info(f"Inserting {len(entities)} canonical entity nodes...")
        for entity in entities:
            self.client.add_entity(entity)

        # 4. Link (Chunk)-[:MENTIONS]->(Entity)
        logger.info("Linking chunks to mentioned entities...")
        for chunk in chunks:
            chunk_lower = chunk.text.lower()
            for entity in entities:
                # Check if entity canonical name or any alias appears in chunk
                is_mentioned = entity.canonical_name.lower() in chunk_lower or any(
                    alias.lower() in chunk_lower for alias in entity.aliases
                )
                if is_mentioned:
                    self.client.link_chunk_to_entity(chunk.chunk_id, entity.canonical_id)

        # 5. Insert Relationship edges with Evidence
        logger.info(f"Inserting {len(relationships)} relationship edges...")
        for rel in relationships:
            self.client.add_relationship(rel)

        stats = self.client.get_stats()
        logger.info(f"Graph population complete: {stats}")
        return stats
