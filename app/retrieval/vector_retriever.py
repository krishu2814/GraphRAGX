"""Dense semantic retriever querying vector storage using text embeddings."""

import logging
from typing import Any

from app.config import get_settings
from app.models.retrieval import RetrievedChunk
from app.vector.embeddings import EmbeddingService, get_embedding_service
from app.vector.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Finds relevant document chunks by comparing query vectors against stored chunk vectors."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
        top_k: int | None = None,
    ) -> None:
        settings = get_settings()
        self.vector_store = vector_store or get_vector_store()
        self.embedding_service = embedding_service or get_embedding_service()
        self.default_top_k = top_k or settings.top_k_chunks

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        document_id: str | None = None,
        access_tier: str | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Perform semantic similarity search for a user query."""
        clean_query = query.strip()
        if not clean_query:
            return []

        limit = top_k if top_k is not None else self.default_top_k

        # Set up filters (e.g. document_id or access_tier)
        filters: dict[str, Any] = {}
        if document_id:
            filters["document_id"] = document_id
        if access_tier:
            filters["access_tier"] = access_tier
        if extra_filters:
            filters.update(extra_filters)

        # 1. Turn query text into an embedding vector
        query_vector = self.embedding_service.embed_text(clean_query)

        # 2. Search Qdrant for nearest neighbor chunks
        chunks = self.vector_store.search(
            query_vector=query_vector,
            top_k=limit,
            filters=filters if filters else None,
        )

        return chunks
