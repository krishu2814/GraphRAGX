"""Dense semantic retriever querying vector storage using text embeddings."""

import logging
from typing import Any

from app.config import get_settings
from app.models.retrieval import RetrievedChunk
from app.vector.embeddings import EmbeddingService, get_embedding_service
from app.vector.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Semantic retriever executing dense vector similarity search over document chunks."""

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
        """Perform semantic similarity retrieval for the given natural language query.
        
        Args:
            query: Natural language query string.
            top_k: Maximum number of chunks to return (defaults to configured top_k_chunks).
            document_id: Optional filter constraining search to a specific document.
            access_tier: Optional security access tier filter.
            extra_filters: Additional arbitrary metadata filter key-value pairs.

        Returns:
            List of ranked RetrievedChunk models sorted by descending similarity score.
        """
        clean_query = query.strip()
        if not clean_query:
            logger.warning("Empty query passed to VectorRetriever; returning empty results.")
            return []

        limit = top_k if top_k is not None else self.default_top_k

        # Construct filters
        filters: dict[str, Any] = {}
        if document_id:
            filters["document_id"] = document_id
        if access_tier:
            filters["access_tier"] = access_tier
        if extra_filters:
            filters.update(extra_filters)

        # Generate query vector
        query_vector = self.embedding_service.embed_text(clean_query)

        # Query vector store
        chunks = self.vector_store.search(
            query_vector=query_vector,
            top_k=limit,
            filters=filters if filters else None,
        )

        logger.info(
            f"VectorRetriever retrieved {len(chunks)} chunks for query: '{clean_query[:50]}...'"
        )
        return chunks
