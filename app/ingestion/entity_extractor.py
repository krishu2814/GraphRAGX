"""Entity extraction engine supporting both LLM structured outputs and deterministic rule-based fallback."""

import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingestion.chunker import DocumentChunk
from app.models.entities import Entity, EntityType

logger = logging.getLogger(__name__)


class RawExtractedEntity(BaseModel):
    """Schema used for structured extraction from text."""

    name: str = Field(..., description="Surface or canonical name of the extracted entity")
    type: EntityType = Field(default=EntityType.OTHER, description="Class or category of the entity")
    description: str = Field(default="", description="Short summary of entity's role or definition")
    aliases: list[str] = Field(default_factory=list, description="Synonyms or abbreviations in text")


class EntityExtractionResult(BaseModel):
    """Wrapper for LLM structured output parsing."""

    entities: list[RawExtractedEntity] = Field(default_factory=list)


class EntityExtractor:
    """Extracts entities from text chunks using OpenAI LLM or deterministic fallback rules."""

    def __init__(self, use_llm_if_available: bool = True) -> None:
        self.settings = get_settings()
        self.use_llm_if_available = use_llm_if_available and bool(self.settings.openai_api_key)

    def extract(self, chunk: DocumentChunk) -> list[Entity]:
        """Extract entities from a single DocumentChunk."""
        if self.use_llm_if_available:
            try:
                return self._extract_with_llm(chunk)
            except Exception as e:
                logger.warning(f"LLM entity extraction failed: {e}. Falling back to deterministic extractor.")
                return self._extract_with_rules(chunk)
        return self._extract_with_rules(chunk)

    def extract_batch(self, chunks: list[DocumentChunk]) -> list[Entity]:
        """Extract entities from a collection of chunks and return combined results."""
        extracted: list[Entity] = []
        for chunk in chunks:
            extracted.extend(self.extract(chunk))
        return extracted

    def _extract_with_llm(self, chunk: DocumentChunk) -> list[Entity]:
        """Call OpenAI with structured output schema to extract entities."""
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        prompt = (
            f"You are a knowledge graph information extraction specialist. "
            f"Extract all significant enterprise entities from the following text chunk.\n\n"
            f"Document Title: {chunk.metadata.title}\n"
            f"Section Path: {chunk.metadata.section_path}\n"
            f"Text:\n\"\"\"\n{chunk.text}\n\"\"\""
        )

        response = client.beta.chat.completions.parse(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": "Extract structured entities with high precision for a knowledge graph."},
                {"role": "user", "content": prompt},
            ],
            response_format=EntityExtractionResult,
            temperature=0.0,
        )

        result = response.choices[0].message.parsed
        entities: list[Entity] = []
        if result:
            for item in result.entities:
                entity_id = self._build_entity_id(item.name, item.type)
                ent = Entity(
                    id=entity_id,
                    name=item.name.strip(),
                    type=item.type,
                    description=item.description.strip(),
                    aliases=item.aliases,
                    metadata={"source_chunk_id": chunk.chunk_id, "document_id": chunk.document_id},
                )
                entities.append(ent)
        return entities

    def _extract_with_rules(self, chunk: DocumentChunk) -> list[Entity]:
        """Deterministic rule-based extractor using pattern matching and domain lexicons."""
        text = chunk.text
        entities: list[Entity] = []
        seen_names: set[str] = set()

        # Domain pattern definitions: (Regex pattern, EntityType, default description generator)
        rules: list[tuple[re.Pattern, EntityType, str]] = [
            # Products
            (re.compile(r"\bProduct\s+(Nova|Orion|Atlas|Vega)\b", re.IGNORECASE), EntityType.PRODUCT, "CloudScale platform product"),
            # Shared Microservices
            (re.compile(r"\b(Identity\s+Service|Policy\s+Engine|Gateway\s+Service|Data\s+Anonymization\s+Service|Billing\s+Engine|Authz\s+Service)\b", re.IGNORECASE), EntityType.SERVICE, "Core platform microservice"),
            # Enterprise Customers
            (re.compile(r"\b(Acme\s+Corp|Globex\s+Corp|Initech)\b", re.IGNORECASE), EntityType.CUSTOMER, "Enterprise customer organization"),
            # Technologies & Protocols
            (re.compile(r"\b(OAuth\s+2\.[01]|PASETO\s*(?:v4)?|PKCE|JWT|Ed25519|mTLS|SAML\s*2\.0|Apache\s+Kafka|Apache\s+Arrow|Aurora\s+PostgreSQL)\b", re.IGNORECASE), EntityType.TECHNOLOGY, "Cryptographic protocol or technology standard"),
            # Cloud Infrastructure
            (re.compile(r"\b(AWS|Azure|Kubernetes|AWS\s+EKS|Azure\s+AKS|Amazon\s+S3|Azure\s+Blob\s+Storage)\b", re.IGNORECASE), EntityType.TECHNOLOGY, "Cloud infrastructure provider or service"),
            # Platform Versions
            (re.compile(r"\b(?:Version\s+)?(v3\.[012]|Version\s+3\.[012])\b", re.IGNORECASE), EntityType.VERSION, "Platform software release"),
            # Incidents
            (re.compile(r"\b(INC-402)\b", re.IGNORECASE), EntityType.INCIDENT, "Production incident report"),
            # Compliance Policies & Frameworks
            (re.compile(r"\b(SOC2(?:\s+Type\s+II)?|GDPR|CCPA|ISO\s*27001|NIST\s*800-53|ITAR)\b", re.IGNORECASE), EntityType.POLICY, "Security, compliance, or regulatory framework"),
            # Subscription Plans
            (re.compile(r"\b(Starter\s+Tier|Growth\s+Tier|Enterprise\s+Tier)\b", re.IGNORECASE), EntityType.PLAN, "Subscription contract tier"),
            # Core Organizations & Key People
            (re.compile(r"\b(CloudScale\s+Systems)\b", re.IGNORECASE), EntityType.ORGANIZATION, "Cloud intelligence and data infrastructure company"),
        ]

        for pattern, ent_type, default_desc in rules:
            for match in pattern.finditer(text):
                raw_name = match.group(0).strip()
                canonical_name = self._normalize_surface_name(raw_name, ent_type)

                if canonical_name.lower() in seen_names:
                    continue
                seen_names.add(canonical_name.lower())

                # Extract surrounding sentence as contextual description
                context_desc = self._find_context_sentence(text, raw_name) or default_desc

                entity_id = self._build_entity_id(canonical_name, ent_type)
                ent = Entity(
                    id=entity_id,
                    name=canonical_name,
                    type=ent_type,
                    description=context_desc,
                    aliases=[raw_name] if raw_name.lower() != canonical_name.lower() else [],
                    metadata={"source_chunk_id": chunk.chunk_id, "document_id": chunk.document_id},
                )
                entities.append(ent)

        return entities

    def _normalize_surface_name(self, name: str, ent_type: EntityType) -> str:
        """Standardize capitalization and remove noise words."""
        clean = re.sub(r"\s+", " ", name).strip()

        # Normalize versions (e.g. "v3.2" -> "Version 3.2")
        if ent_type == EntityType.VERSION:
            v_match = re.search(r"3\.[012]", clean)
            if v_match:
                return f"Version {v_match.group(0)}"

        # Standardize product names
        p_match = re.match(r"(?:Product\s+)?(Nova|Orion|Atlas|Vega)", clean, re.IGNORECASE)
        if p_match and ent_type == EntityType.PRODUCT:
            return f"Product {p_match.group(1).capitalize()}"

        # Standardize known services
        if "identity" in clean.lower():
            return "Identity Service"
        if "policy" in clean.lower():
            return "Policy Engine"
        if "gateway" in clean.lower():
            return "Gateway Service"
        if "anonymization" in clean.lower():
            return "Data Anonymization Service"
        if "billing" in clean.lower():
            return "Billing Engine"
        if "authz" in clean.lower():
            return "Authz Service"

        # Standardize technologies
        if "oauth 2.1" in clean.lower():
            return "OAuth 2.1"
        if "oauth 2.0" in clean.lower():
            return "OAuth 2.0"
        if "soc2" in clean.lower():
            return "SOC2 Type II"

        return clean

    def _build_entity_id(self, name: str, ent_type: EntityType) -> str:
        """Create a deterministic slug ID e.g. entity:product:nova."""
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return f"entity:{ent_type.value.lower()}:{slug}"

    def _find_context_sentence(self, text: str, mention: str) -> str:
        """Find the sentence containing the mention to use as description."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            if mention.lower() in s.lower():
                clean_s = s.strip()
                if len(clean_s) > 200:
                    clean_s = clean_s[:197] + "..."
                return clean_s
        return ""
