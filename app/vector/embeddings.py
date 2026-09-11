"""Embedding service supporting OpenAI text-embedding models with deterministic offline fallback."""

import hashlib
import logging
import re
from typing import Protocol, runtime_checkable
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingService(Protocol):
    """Interface for text embedding providers."""

    dimension: int

    def embed_text(self, text: str) -> list[float]:
        """Generate a dense vector embedding for a single text string."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate dense vector embeddings for a batch of text strings."""
        ...


class DefaultEmbeddingService:
    """Production embedding service with automatic offline fallback.
    
    When `openai_api_key` is configured, utilizes OpenAI's embedding API.
    When offline or without an API key, utilizes a deterministic feature-hashing
    dense projection with L2 unit normalization, ensuring zero external dependencies.
    """

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
                logger.info(f"OpenAI embedding client initialized with model '{self.model}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}. Falling back to offline embeddings.")
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
                response = self._client.embeddings.create(
                    input=texts,
                    model=self.model,
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                logger.warning(f"OpenAI embedding API call failed: {e}. Falling back to deterministic embeddings.")

        return [self._deterministic_dense_vector(t) for t in texts]

    def _deterministic_dense_vector(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-semantic dense vector using feature hashing.
        
        Extracts words and character n-grams, projects them via hashing into a vector of
        length `self.dimension`, and normalizes with L2 norm to guarantee cosine compatibility.
        """
        if not text or not text.strip():
            vec = np.zeros(self.dimension, dtype=np.float32)
            vec[0] = 1.0
            return vec.tolist()

        vec = np.zeros(self.dimension, dtype=np.float32)
        clean = text.lower()
        words = re.findall(r"\b\w+\b", clean)

        # 1. Word token projections
        for word in words:
            h = hashlib.sha256(word.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dimension
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            weight = 2.0 if any(c.isupper() for c in word) or len(word) > 5 else 1.0
            vec[idx] += sign * weight

        # 2. Character 3-gram projections for subword robustness
        for i in range(len(clean) - 2):
            ngram = clean[i : i + 3]
            h = hashlib.sha256(ngram.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dimension
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign * 0.35

        # 3. L2 Normalization
        norm = float(np.linalg.norm(vec))
        if norm > 1e-12:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service(force_new: bool = False) -> EmbeddingService:
    """Singleton factory for obtaining the application's EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None or force_new:
        _embedding_service_instance = DefaultEmbeddingService()
    return _embedding_service_instance
