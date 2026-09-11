"""Domain models for retrieval results across vector, graph, multi-hop, and hybrid fusion."""

from typing import Any
from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A textual document chunk retrieved via semantic vector search or evidence lookup."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document identifier")
    text: str = Field(..., description="Textual content of the chunk")
    score: float = Field(default=0.0, description="Similarity or retrieval score")
    rank: int = Field(default=1, description="Rank in retrieval result list")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata (headers, section, etc.)")


class GraphFact(BaseModel):
    """An individual relational fact extracted from the knowledge graph."""

    source_entity: str = Field(..., description="Source entity ID")
    source_name: str = Field(default="", description="Display name of source entity")
    relation: str = Field(..., description="Relationship type/predicate connecting the entities")
    target_entity: str = Field(..., description="Target entity ID")
    target_name: str = Field(default="", description="Display name of target entity")
    evidence_chunk_id: str = Field(default="", description="Source chunk grounding this fact")
    confidence: float = Field(default=1.0, description="Extraction or path confidence")


class RetrievalPath(BaseModel):
    """A multi-hop path traversed through the knowledge graph."""

    entities: list[str] = Field(default_factory=list, description="Ordered sequence of entity names or IDs")
    relationships: list[str] = Field(default_factory=list, description="Ordered sequence of relationship types")
    length: int = Field(default=0, description="Number of hops in the path")
    score: float = Field(default=1.0, description="Path relevance score")
    evidence_chunk_ids: list[str] = Field(default_factory=list, description="Associated chunk IDs validating hops")
    explanation: str = Field(default="", description="Human-readable explanation of this relational path")

    def to_cypher_like(self) -> str:
        """Render path as a Cypher-like ASCII string, e.g. (A)-[:USES]->(B)-[:DEPENDS_ON]->(C)."""
        if not self.entities:
            return ""
        if len(self.entities) == 1:
            return f"({self.entities[0]})"
        parts = []
        for i, ent in enumerate(self.entities):
            parts.append(f"({ent})")
            if i < len(self.relationships):
                parts.append(f"-[:{self.relationships[i]}]->")
        return "".join(parts)


class CommunitySummary(BaseModel):
    """A thematic cluster/community of entities and its generated summary."""

    community_id: str = Field(..., description="Unique community cluster identifier")
    name: str = Field(..., description="Descriptive title of the community (e.g., Security & Identity)")
    level: int = Field(default=0, description="Hierarchy level (0 = fine-grained, 1 = coarse)")
    entities: list[str] = Field(default_factory=list, description="Entities belonging to this cluster")
    summary_text: str = Field(default="", description="High-level narrative summary of this community")
    key_relationships: list[str] = Field(default_factory=list, description="Prominent relationships within the community")


class FusionResult(BaseModel):
    """Fused candidate item combining vector similarity ranks and graph topological scores."""

    chunk_id: str = Field(..., description="Target chunk ID")
    document_id: str = Field(..., description="Source document identifier")
    text: str = Field(..., description="Chunk content")
    vector_score: float = Field(default=0.0, description="Dense vector similarity score")
    vector_rank: int | None = Field(default=None, description="Rank in pure vector retrieval")
    graph_score: float = Field(default=0.0, description="Score derived from graph topology/evidence")
    graph_rank: int | None = Field(default=None, description="Rank in graph retrieval")
    entity_score: float = Field(default=0.0, description="Score based on direct entity overlap")
    rrf_score: float = Field(default=0.0, description="Reciprocal Rank Fusion score")
    final_score: float = Field(default=0.0, description="Final weighted combined score")
    contributing_paths: list[RetrievalPath] = Field(default_factory=list, description="Graph paths that supported this chunk")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class MultiHopResult(BaseModel):
    """Result of multi-hop graph traversal starting from a seed entity."""

    seed_entity: str = Field(..., description="Query or seed entity used to begin traversal")
    paths: list[RetrievalPath] = Field(default_factory=list, description="Discovered relational paths")
    facts: list[GraphFact] = Field(default_factory=list, description="Unique relational facts discovered along paths")
    evidence_chunks: list[RetrievedChunk] = Field(default_factory=list, description="Grounded source text chunks validating paths")

