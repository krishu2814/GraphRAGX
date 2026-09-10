"""Domain models for relationships and evidence in the knowledge graph."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class RelationType(str, Enum):
    """Types of edges/predicates connecting entities in the enterprise graph."""

    DEPENDS_ON = "DEPENDS_ON"
    USES = "USES"
    AFFECTS = "AFFECTS"
    INTRODUCED_IN = "INTRODUCED_IN"
    SUPPORTS = "SUPPORTS"
    DEPLOYS_TO = "DEPLOYS_TO"
    INTEGRATES_WITH = "INTEGRATES_WITH"
    COMPLIES_WITH = "COMPLIES_WITH"
    OWNED_BY = "OWNED_BY"
    PART_OF = "PART_OF"
    RELATED_TO = "RELATED_TO"


class Evidence(BaseModel):
    """Source evidence grounding an extracted fact or relationship back to a document chunk."""

    chunk_id: str = Field(..., description="ID of chunk where the relationship is documented")
    document_id: str = Field(..., description="Parent document identifier")
    text: str = Field(..., description="Exact or near-verbatim quote from the chunk supporting the relation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score")


class Relationship(BaseModel):
    """A directed edge connecting two entities with associated evidence and weight."""

    id: str = Field(..., description="Unique relationship identifier (e.g., rel:nova:depends_on:identity_service)")
    source_id: str = Field(..., description="Origin entity ID")
    target_id: str = Field(..., description="Destination entity ID")
    type: RelationType = Field(default=RelationType.RELATED_TO, description="Semantic edge type")
    description: str = Field(default="", description="Description of the relational connection")
    weight: float = Field(default=1.0, ge=0.0, description="Connection strength or frequency weight")
    evidence: list[Evidence] = Field(default_factory=list, description="Grounding chunks and source quotes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom edge attributes")

    def add_evidence(self, chunk_id: str, document_id: str, text: str, confidence: float = 1.0) -> None:
        """Append evidence if not already recorded from this chunk."""
        for ev in self.evidence:
            if ev.chunk_id == chunk_id:
                return
        self.evidence.append(
            Evidence(chunk_id=chunk_id, document_id=document_id, text=text, confidence=confidence)
        )
