"""Metadata enrichment and validation for documents and chunks."""

from enum import Enum
import re
from typing import Any
from pydantic import BaseModel, Field


class AccessTier(str, Enum):
    """Data classification tiers for enterprise documents and chunks."""

    PUBLIC = "Public"
    INTERNAL = "Internal"
    CONFIDENTIAL = "Confidential"
    RESTRICTED = "Restricted"

    @classmethod
    def from_str(cls, value: str) -> "AccessTier":
        """Normalize string to matching AccessTier enum."""
        clean = value.strip().capitalize()
        for tier in cls:
            if tier.value.lower() == clean.lower():
                return tier
        return cls.INTERNAL


class ChunkMetadata(BaseModel):
    """Enriched metadata accompanying each chunk throughout the retrieval pipeline."""

    document_id: str = Field(..., description="Parent document identifier")
    title: str = Field(..., description="Document title")
    department: str = Field(default="General", description="Department of origin")
    access_tier: AccessTier = Field(default=AccessTier.INTERNAL, description="Access security tier")
    version: str = Field(default="1.0", description="Product or document version")
    section_title: str = Field(default="", description="Immediate section heading title")
    section_path: str = Field(default="", description="Hierarchical breadcrumb section path")
    char_count: int = Field(default=0, description="Number of characters in the chunk")
    word_count: int = Field(default=0, description="Word count in chunk text")
    estimated_tokens: int = Field(default=0, description="Heuristic token estimation (~4 chars/token)")
    entity_hints: list[str] = Field(default_factory=list, description="Candidate entity hints detected in text")
    custom_attributes: dict[str, Any] = Field(default_factory=dict, description="Arbitrary frontmatter key-values")


class MetadataEnricher:
    """Extracts and enriches metadata for document chunks."""

    # Common domain entities to extract as candidate hints during chunking
    KNOWN_ENTITY_PATTERNS = [
        re.compile(r"\bProduct\s+(Nova|Orion|Atlas|Vega)\b", re.IGNORECASE),
        re.compile(r"\b(Identity\s+Service|Policy\s+Engine|Gateway\s+Service|Data\s+Anonymization\s+Service|Billing\s+Engine|Authz\s+Service)\b", re.IGNORECASE),
        re.compile(r"\b(Acme\s+Corp|Globex\s+Corp|Initech)\b", re.IGNORECASE),
        re.compile(r"\b(OAuth\s+2\.[01]|PASETO|JWT|Ed25519|PKCE|mTLS|SAML|RBAC|ABAC|SOC2|GDPR|CCPA)\b", re.IGNORECASE),
        re.compile(r"\b(AWS|Azure|Kubernetes|EKS|AKS|Kafka|PostgreSQL|Aurora)\b", re.IGNORECASE),
        re.compile(r"\b(Version\s+3\.[012]|INC-402)\b", re.IGNORECASE),
    ]

    def enrich(
        self,
        text: str,
        document_id: str,
        title: str,
        department: str = "General",
        access_tier_str: str = "Internal",
        version: str = "1.0",
        section_title: str = "",
        section_path: str = "",
        custom_metadata: dict[str, Any] | None = None,
    ) -> ChunkMetadata:
        """Construct validated and enriched ChunkMetadata object."""
        access_tier = AccessTier.from_str(access_tier_str)
        char_count = len(text)
        word_count = len(text.split())
        estimated_tokens = max(1, char_count // 4)

        # Detect candidate entity hints to assist downstream entity extractors
        entity_hints = self.detect_entity_hints(text)

        return ChunkMetadata(
            document_id=document_id,
            title=title,
            department=department,
            access_tier=access_tier,
            version=version,
            section_title=section_title,
            section_path=section_path,
            char_count=char_count,
            word_count=word_count,
            estimated_tokens=estimated_tokens,
            entity_hints=entity_hints,
            custom_attributes=custom_metadata or {},
        )

    def detect_entity_hints(self, text: str) -> list[str]:
        """Scan text for prominent enterprise entity patterns."""
        hints: set[str] = set()
        for pattern in self.KNOWN_ENTITY_PATTERNS:
            for match in pattern.finditer(text):
                matched_str = match.group(0).strip()
                # Clean up whitespace
                clean = re.sub(r"\s+", " ", matched_str)
                hints.add(clean)
        return sorted(hints)
