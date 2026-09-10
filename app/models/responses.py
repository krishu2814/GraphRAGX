"""Domain models for system responses, traceable citations, and strategy comparisons."""

from typing import Any
from pydantic import BaseModel, Field
from app.models.query import RetrievalStrategy
from app.models.retrieval import GraphFact, RetrievalPath, RetrievedChunk


class Citation(BaseModel):
    """A traceable citation grounding a statement in the generated answer back to source text."""

    citation_id: str = Field(..., description="Unique reference marker (e.g. [1], [2])")
    chunk_id: str = Field(..., description="Source chunk ID supporting the statement")
    document_id: str = Field(..., description="Source document name")
    quote: str = Field(default="", description="Relevant sentence or fragment cited")
    relevance_score: float = Field(default=1.0, description="Relevance score of cited evidence")


class QueryResponse(BaseModel):
    """End-to-end response returned by GraphRAGX."""

    query: str = Field(..., description="User query submitted")
    answer: str = Field(..., description="Synthesized grounded answer")
    strategy: RetrievalStrategy = Field(..., description="Retrieval strategy executed")
    citations: list[Citation] = Field(default_factory=list, description="Verified citations")
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list, description="Retrieved context chunks")
    graph_facts: list[GraphFact] = Field(default_factory=list, description="Relational facts used")
    traversal_paths: list[RetrievalPath] = Field(default_factory=list, description="Graph paths traversed")
    latency_ms: float = Field(default=0.0, description="Total execution time in milliseconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Diagnostic and trace metadata")


class ComparisonResult(BaseModel):
    """Side-by-side comparison of results across Vector, Graph, and Hybrid retrieval strategies."""

    query: str = Field(..., description="Evaluated query")
    vector_response: QueryResponse = Field(..., description="Response using pure dense vector search")
    graph_response: QueryResponse = Field(..., description="Response using knowledge graph traversal")
    hybrid_response: QueryResponse = Field(..., description="Response using hybrid fusion (RRF)")
    analysis: str = Field(default="", description="Differential analysis highlighting what Graph and Hybrid discovered")
