"""Vector storage engine integrating Qdrant with in-memory and production support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
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


class QdrantVectorStore:
    """Manages chunk embeddings in Qdrant (in-memory or remote server)."""

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
            self.client = QdrantClient(":memory:")
        else:
            try:
                self.client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    timeout=3.0,
                )
                self.client.get_collections()
            except Exception as e:
                logger.warning(f"Could not connect to Qdrant ({e}). Using in-memory client.")
                self.client = QdrantClient(":memory:")

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't already exist."""
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Save chunks and their vector embeddings into Qdrant."""
        if not chunks:
            return 0

        if embeddings is None:
            texts = [c.text for c in chunks]
            embeddings = self.embedding_service.embed_batch(texts)

        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            # Deterministic UUID from chunk_id
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

            meta_dict: dict[str, Any] = {}
            if hasattr(chunk, "metadata"):
                if hasattr(chunk.metadata, "model_dump"):
                    meta_dict = chunk.metadata.model_dump(mode="json")
                elif isinstance(chunk.metadata, dict):
                    meta_dict = chunk.metadata

            payload = {
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
        return len(points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Search Qdrant for the most similar chunks."""
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

        results: list[RetrievedChunk] = []
        for rank_idx, point in enumerate(res.points):
            payload = point.payload or {}
            results.append(
                RetrievedChunk(
                    chunk_id=payload.get("chunk_id", str(point.id)),
                    document_id=payload.get("document_id", ""),
                    text=payload.get("text", ""),
                    score=float(point.score) if point.score is not None else 0.0,
                    rank=rank_idx + 1,
                    metadata=payload,
                )
            )
        return results

    def count(self) -> int:
        try:
            return self.client.count(collection_name=self.collection_name).count
        except Exception:
            return 0

    def clear(self) -> None:
        try:
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            self._ensure_collection()
        except Exception as e:
            logger.warning(f"Error clearing collection: {e}")


VectorStore = QdrantVectorStore

_vector_store_instance: QdrantVectorStore | None = None


def get_vector_store(
    force_new: bool = False,
    in_memory: bool | None = None,
    collection_name: str | None = None,
) -> QdrantVectorStore:
    global _vector_store_instance
    if _vector_store_instance is None or force_new or in_memory is not None or collection_name is not None:
        store = QdrantVectorStore(in_memory=in_memory, collection_name=collection_name)
        if not force_new and in_memory is None and collection_name is None:
            _vector_store_instance = store
        return store
    return _vector_store_instance
