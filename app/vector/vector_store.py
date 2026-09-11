"""Vector storage engine integrating Qdrant with in-memory and production support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.models.retrieval import RetrievedChunk
from app.vector.embeddings import EmbeddingService, get_embedding_service

if TYPE_CHECKING:
    from app.ingestion.chunker import DocumentChunk

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol defining the storage and similarity search contract."""

    collection_name: str
    dimension: int

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Store or update document chunks with their dense vector embeddings."""
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Perform dense semantic similarity search against the vector index."""
        ...

    def count(self) -> int:
        """Return the number of points in the vector store."""
        ...

    def clear(self) -> None:
        """Empty or reset the vector store collection."""
        ...


class QdrantVectorStore:
    """Qdrant-backed vector storage implementation.
    
    Operates seamlessly in in-memory mode (`:memory:`) or connects to remote Qdrant instances.
    """

    def __init__(
        self,
        client: QdrantClient | None = None,
        collection_name: str | None = None,
        dimension: int | None = None,
        embedding_service: EmbeddingService | None = None,
        in_memory: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.collection_name = collection_name or settings.qdrant_collection
        self.dimension = dimension or settings.embedding_dimension
        self.embedding_service = embedding_service or get_embedding_service()
        use_in_mem = in_memory if in_memory is not None else settings.use_in_memory_vector

        if client is not None:
            self.client = client
        elif use_in_mem:
            logger.info(f"Initializing in-memory Qdrant instance for collection '{self.collection_name}'.")
            self.client = QdrantClient(":memory:")
        else:
            try:
                logger.info(f"Connecting to Qdrant server at {settings.qdrant_url}...")
                self.client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    timeout=3.0,
                )
                # Probe connection
                self.client.get_collections()
            except Exception as e:
                logger.warning(
                    f"Could not connect to Qdrant at {settings.qdrant_url}: {e}. "
                    "Falling back to in-memory Qdrant client."
                )
                self.client = QdrantClient(":memory:")

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the target collection with cosine distance if it doesn't already exist."""
        try:
            exists = self.client.collection_exists(self.collection_name)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
                logger.info(
                    f"Created Qdrant collection '{self.collection_name}' (dim={self.dimension}, metric=COSINE)."
                )
        except Exception as e:
            logger.error(f"Error checking or creating collection '{self.collection_name}': {e}")
            raise

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Idempotently insert or update document chunks with their dense embeddings."""
        if not chunks:
            return 0

        if embeddings is None:
            texts = [c.text for c in chunks]
            embeddings = self.embedding_service.embed_batch(texts)

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch between number of chunks ({len(chunks)}) and embeddings ({len(embeddings)})"
            )

        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            # Deterministic UUID5 for idempotent updates
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            
            # Extract metadata safely
            meta_dict: dict[str, Any] = {}
            if hasattr(chunk, "metadata"):
                if hasattr(chunk.metadata, "model_dump"):
                    meta_dict = chunk.metadata.model_dump(mode="json")
                elif isinstance(chunk.metadata, dict):
                    meta_dict = chunk.metadata

            payload: dict[str, Any] = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "index": getattr(chunk, "index", 0),
                "title": meta_dict.get("title", ""),
                "department": meta_dict.get("department", "General"),
                "section_title": meta_dict.get("section_title", ""),
                "section_path": meta_dict.get("section_path", ""),
                "access_tier": str(meta_dict.get("access_tier", "Internal")),
                "entity_hints": meta_dict.get("entity_hints", []),
                "metadata": meta_dict,
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} points into Qdrant collection '{self.collection_name}'.")
        return len(points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Perform dense semantic search and return structured RetrievedChunk models."""
        query_filter = None
        if filters:
            conditions = []
            for key, val in filters.items():
                if val is not None:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))
            if conditions:
                query_filter = Filter(must=conditions)

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
        )

        retrieved: list[RetrievedChunk] = []
        for rank_idx, point in enumerate(res.points):
            payload = point.payload or {}
            retrieved.append(
                RetrievedChunk(
                    chunk_id=payload.get("chunk_id", str(point.id)),
                    document_id=payload.get("document_id", ""),
                    text=payload.get("text", ""),
                    score=float(point.score) if point.score is not None else 0.0,
                    rank=rank_idx + 1,
                    metadata=payload,
                )
            )

        return retrieved

    def count(self) -> int:
        """Return the number of points in the collection."""
        try:
            return self.client.count(collection_name=self.collection_name).count
        except Exception:
            return 0

    def clear(self) -> None:
        """Clear all points from the collection."""
        try:
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            self._ensure_collection()
        except Exception as e:
            logger.warning(f"Error clearing collection '{self.collection_name}': {e}")


_vector_store_instance: VectorStore | None = None


def get_vector_store(
    force_new: bool = False,
    in_memory: bool | None = None,
    collection_name: str | None = None,
) -> VectorStore:
    """Singleton factory for obtaining the application's VectorStore."""
    global _vector_store_instance
    if _vector_store_instance is None or force_new or in_memory is not None or collection_name is not None:
        store = QdrantVectorStore(in_memory=in_memory, collection_name=collection_name)
        if not force_new and in_memory is None and collection_name is None:
            _vector_store_instance = store
        return store
    return _vector_store_instance
