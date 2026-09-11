"""End-to-end ingestion pipeline coordinating loading, chunking, extraction, resolution, and graph construction."""

import logging
from pathlib import Path
import time
from typing import Any
from pydantic import BaseModel, Field

from app.config import get_settings
from app.graph.neo4j_client import GraphClient, get_graph_client
from app.ingestion.chunker import DocumentChunk, SemanticChunker
from app.ingestion.entity_extractor import EntityExtractor
from app.ingestion.entity_resolution import EntityResolver
from app.ingestion.graph_builder import GraphBuilder
from app.ingestion.loaders import LoadedDocument, MarkdownLoader
from app.ingestion.relation_extractor import RelationExtractor
from app.models.entities import CanonicalEntity
from app.models.relationships import Relationship
from app.vector.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class IngestionSummary(BaseModel):
    """Execution metrics and diagnostic report returned upon ingestion pipeline completion."""

    documents_loaded: int = Field(..., description="Number of markdown files ingested")
    chunks_created: int = Field(..., description="Total semantic chunks produced")
    entities_extracted: int = Field(..., description="Raw entity mentions detected")
    canonical_entities_count: int = Field(..., description="Deduplicated canonical entity nodes")
    raw_relationships_extracted: int = Field(..., description="Raw relation mentions found")
    resolved_relationships_count: int = Field(..., description="Consolidated relationship edges")
    graph_stats: dict[str, int] = Field(default_factory=dict, description="Final graph database node/edge counts")
    vector_points_indexed: int = Field(default=0, description="Total chunks indexed into the vector store")
    duration_ms: float = Field(default=0.0, description="Total pipeline execution duration in milliseconds")


class IngestionPipeline:
    """Orchestrates end-to-end knowledge ingestion into GraphRAGX graph and vector stores."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        use_llm: bool = False,
        client: GraphClient | None = None,
        vector_store: VectorStore | None = None,
        index_vectors: bool = True,
    ) -> None:
        self.settings = get_settings()
        self.data_dir = Path(data_dir) if data_dir else Path("data/documents")
        self.chunk_size = chunk_size or self.settings.chunk_size
        self.chunk_overlap = chunk_overlap or self.settings.chunk_overlap
        self.use_llm = use_llm
        self.index_vectors = index_vectors

        self.client = client or get_graph_client()
        self.vector_store = vector_store or get_vector_store()
        self.loader = MarkdownLoader()
        self.chunker = SemanticChunker(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        self.entity_extractor = EntityExtractor(use_llm_if_available=self.use_llm)
        self.relation_extractor = RelationExtractor(use_llm_if_available=self.use_llm)
        self.resolver = EntityResolver()
        self.builder = GraphBuilder(self.client)

    def run(self) -> IngestionSummary:
        """Execute the full ingestion pipeline from documents to graph database."""
        start_time = time.perf_counter()
        logger.info(f"Starting ingestion pipeline from source directory: {self.data_dir.resolve()}")

        # 1. Load documents
        documents = self.loader.load_directory(self.data_dir)
        logger.info(f"Step 1/5: Loaded {len(documents)} documents.")

        # 2. Chunk documents
        chunks = self.chunker.chunk_documents(documents)
        logger.info(f"Step 2/5: Generated {len(chunks)} semantic chunks.")

        # 3. Extract raw entities & relationships
        raw_entities = self.entity_extractor.extract_batch(chunks)
        raw_relationships = self.relation_extractor.extract_batch(chunks)
        logger.info(
            f"Step 3/5: Extracted {len(raw_entities)} entity mentions and "
            f"{len(raw_relationships)} relationship mentions."
        )

        # 4. Resolve entities & deduplicate relationships
        canonical_entities = self.resolver.resolve_entities(raw_entities)
        resolved_relationships = self.resolver.resolve_relationships(raw_relationships, canonical_entities)
        logger.info(
            f"Step 4/5: Consolidated into {len(canonical_entities)} canonical entities and "
            f"{len(resolved_relationships)} unique grounded relationship edges."
        )

        # 5. Populate graph database
        graph_stats = self.builder.populate(
            chunks=chunks,
            entities=canonical_entities,
            relationships=resolved_relationships,
            documents=documents,
        )
        logger.info(f"Step 5/6: Graph successfully populated.")

        # 6. Populate vector store
        vector_points_indexed = 0
        if self.index_vectors and self.vector_store is not None:
            logger.info(f"Step 6/6: Indexing {len(chunks)} chunks into vector store...")
            vector_points_indexed = self.vector_store.upsert_chunks(chunks)
            logger.info(f"Step 6/6: Indexed {vector_points_indexed} points into vector store.")
        else:
            logger.info("Step 6/6: Vector indexing skipped.")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return IngestionSummary(
            documents_loaded=len(documents),
            chunks_created=len(chunks),
            entities_extracted=len(raw_entities),
            canonical_entities_count=len(canonical_entities),
            raw_relationships_extracted=len(raw_relationships),
            resolved_relationships_count=len(resolved_relationships),
            graph_stats=graph_stats,
            vector_points_indexed=vector_points_indexed,
            duration_ms=round(elapsed_ms, 2),
        )
