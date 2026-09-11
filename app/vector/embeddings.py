"""Embedding service supporting OpenAI text-embedding models with deterministic offline fallback."""

from __future__ import annotations

import hashlib
import logging
import re
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates text embeddings using OpenAI or a deterministic offline fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension
        self._client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}. Using offline embeddings.")
                self._client = None

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in batch."""
        if not texts:
            return []

        if self._client:
            try:
                response = self._client.embeddings.create(input=texts, model=self.model)
                return [d.embedding for d in response.data]
            except Exception as e:
                logger.warning(f"OpenAI error: {e}. Using offline embeddings.")

        return [self._deterministic_dense_vector(t) for t in texts]

    def _deterministic_dense_vector(self, text: str) -> list[float]:
        """Simple word-hashing vectorizer fallback when offline."""
        if not text.strip():
            vec = np.zeros(self.dimension, dtype=np.float32)
            vec[0] = 1.0
            return vec.tolist()

        vec = np.zeros(self.dimension, dtype=np.float32)
        words = re.findall(r"\b\w+\b", text.lower())

        # 1. Project words into vector buckets
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h & 1) == 0 else -1.0
            weight = 2.0 if len(word) > 5 else 1.0
            vec[idx] += sign * weight

        # 2. Add character 3-grams for subword similarity
        clean = text.lower()
        for i in range(len(clean) - 2):
            h = int(hashlib.md5(clean[i : i + 3].encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h & 1) == 0 else -1.0
            vec[idx] += sign * 0.35

        # 3. Normalize by L2 length so cosine similarity is just the dot product
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()


DefaultEmbeddingService = EmbeddingService

_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service(force_new: bool = False) -> EmbeddingService:
    """Factory to get the global singleton EmbeddingService instance."""
    global _embedding_service_instance
    if _embedding_service_instance is None or force_new:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
