"""Application configuration and settings management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for GraphRAGX."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Graph Database (Neo4j)
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j bolt connection URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="graphragx_secret", description="Neo4j password")
    neo4j_database: str = Field(default="neo4j", description="Neo4j database name")
    use_in_memory_graph: bool = Field(
        default=True,
        description="Whether to use in-memory NetworkX graph driver when Neo4j is offline or unavailable",
    )

    # Vector Database (Qdrant)
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant service URL or :memory:")
    qdrant_api_key: str = Field(default="", description="Qdrant API key if required")
    qdrant_collection: str = Field(default="graphragx_chunks", description="Collection name for document chunks")
    use_in_memory_vector: bool = Field(
        default=True,
        description="Whether to use in-memory vector index when Qdrant is unavailable",
    )

    # LLM & Embeddings
    openai_api_key: str = Field(default="", description="OpenAI API key (optional; fallback extractors activate when empty)")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model identifier")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model identifier")
    embedding_dimension: int = Field(default=1536, description="Embedding vector dimension")

    # Ingestion & Chunking
    chunk_size: int = Field(default=500, description="Target token/character size for semantic chunks")
    chunk_overlap: int = Field(default=100, description="Chunk overlap size")

    # Retrieval & RRF Weights
    default_retrieval_strategy: Literal["vector", "graph", "hybrid", "multi_hop", "global"] = Field(
        default="hybrid",
        description="Default retrieval strategy",
    )
    top_k_chunks: int = Field(default=5, description="Number of top chunks to return")
    max_graph_hops: int = Field(default=2, description="Maximum graph traversal hop depth")
    max_graph_facts: int = Field(default=15, description="Maximum graph facts to assemble in context")
    rrf_k: int = Field(default=60, description="Reciprocal Rank Fusion smoothing parameter k")
    vector_weight: float = Field(default=0.5, description="Relative weight of vector score in RRF fusion")
    graph_weight: float = Field(default=0.3, description="Relative weight of graph score in RRF fusion")
    entity_weight: float = Field(default=0.2, description="Relative weight of entity score in RRF fusion")

    # System & Logging
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    debug: bool = Field(default=True, description="Enable verbose diagnostic retrieval traces")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
