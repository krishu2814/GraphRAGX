"""Domain models for entities and entity types in the knowledge graph."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Categorical classification of entities in the enterprise knowledge graph."""

    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    CUSTOMER = "CUSTOMER"
    TECHNOLOGY = "TECHNOLOGY"
    VERSION = "VERSION"
    PLAN = "PLAN"
    ORGANIZATION = "ORGANIZATION"
    POLICY = "POLICY"
    INCIDENT = "INCIDENT"
    CONCEPT = "CONCEPT"
    OTHER = "OTHER"


class Entity(BaseModel):
    """An individual entity extracted from documents or maintained in the knowledge graph."""

    id: str = Field(..., description="Unique entity identifier (e.g., entity:product:nova)")
    name: str = Field(..., description="Canonical or surface display name of the entity")
    type: EntityType = Field(default=EntityType.OTHER, description="Class of the entity")
    description: str = Field(default="", description="Brief summary or role of the entity")
    aliases: list[str] = Field(default_factory=list, description="Alternative names or synonyms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary attributes (e.g. department, tier)")

    def add_alias(self, alias: str) -> None:
        """Add an alias if not already present."""
        clean = alias.strip()
        if clean and clean.lower() != self.name.lower() and clean not in self.aliases:
            self.aliases.append(clean)


class CanonicalEntity(BaseModel):
    """A resolved entity representing a unified concept across multiple document mentions."""

    canonical_id: str = Field(..., description="Stable unique canonical entity identifier")
    canonical_name: str = Field(..., description="Primary standard name")
    primary_type: EntityType = Field(default=EntityType.OTHER, description="Resolved entity type")
    description: str = Field(default="", description="Aggregated entity description")
    aliases: list[str] = Field(default_factory=list, description="All known alias surface forms")
    source_mentions: list[str] = Field(default_factory=list, description="Raw surface strings encountered")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Consolidated metadata")
