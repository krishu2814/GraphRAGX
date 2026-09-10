"""Relationship extraction engine with exact evidence provenance and dual LLM/rule fallback."""

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingestion.chunker import DocumentChunk
from app.models.entities import Entity, EntityType
from app.models.relationships import Evidence, Relationship, RelationType

logger = logging.getLogger(__name__)


class RawExtractedRelation(BaseModel):
    """Schema for structured relationship extraction."""

    source_name: str = Field(..., description="Name of source entity")
    target_name: str = Field(..., description="Name of target entity")
    type: RelationType = Field(default=RelationType.RELATED_TO, description="Semantic edge type")
    description: str = Field(default="", description="Description of the relational connection")
    evidence_quote: str = Field(..., description="Exact verbatim text sentence from chunk validating relation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")


class RelationExtractionResult(BaseModel):
    """Wrapper for LLM structured relation extraction."""

    relationships: list[RawExtractedRelation] = Field(default_factory=list)


class RelationExtractor:
    """Extracts directed relationships between entities grounded in source chunk quotes."""

    def __init__(self, use_llm_if_available: bool = True) -> None:
        self.settings = get_settings()
        self.use_llm_if_available = use_llm_if_available and bool(self.settings.openai_api_key)

    def extract(self, chunk: DocumentChunk, entities: list[Entity] | None = None) -> list[Relationship]:
        """Extract relationships from a single chunk."""
        if self.use_llm_if_available:
            try:
                return self._extract_with_llm(chunk, entities or [])
            except Exception as e:
                logger.warning(f"LLM relation extraction failed: {e}. Using deterministic fallback.")
                return self._extract_with_rules(chunk, entities)
        return self._extract_with_rules(chunk, entities)

    def extract_batch(
        self,
        chunks: list[DocumentChunk],
        chunk_entities_map: dict[str, list[Entity]] | None = None,
    ) -> list[Relationship]:
        """Extract relationships across multiple chunks."""
        relationships: list[Relationship] = []
        for chunk in chunks:
            ents = chunk_entities_map.get(chunk.chunk_id) if chunk_entities_map else None
            relationships.extend(self.extract(chunk, ents))
        return relationships

    def _extract_with_llm(self, chunk: DocumentChunk, entities: list[Entity]) -> list[Relationship]:
        """Call OpenAI structured outputs to extract relationships."""
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        entity_names = [e.name for e in entities]
        prompt = (
            f"You are a knowledge graph relation extractor. Extract directed relationships connecting entities in this chunk.\n\n"
            f"Known Entities: {', '.join(entity_names) if entity_names else 'Detect in text'}\n"
            f"Chunk Text:\n\"\"\"\n{chunk.text}\n\"\"\""
        )

        response = client.beta.chat.completions.parse(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": "Extract strictly grounded entity relationships with exact evidence quotes."},
                {"role": "user", "content": prompt},
            ],
            response_format=RelationExtractionResult,
            temperature=0.0,
        )

        parsed = response.choices[0].message.parsed
        results: list[Relationship] = []
        if parsed:
            for item in parsed.relationships:
                rel = self._create_relationship(
                    source_name=item.source_name,
                    target_name=item.target_name,
                    rel_type=item.type,
                    description=item.description,
                    evidence_text=item.evidence_quote,
                    chunk=chunk,
                    confidence=item.confidence,
                )
                results.append(rel)
        return results

    def _extract_with_rules(self, chunk: DocumentChunk, entities: list[Entity] | None = None) -> list[Relationship]:
        """Deterministic relationship extraction based on co-occurrence and linguistic predicates."""
        # If entities weren't passed, use entity extractor in rule mode to find candidates
        if entities is None:
            from app.ingestion.entity_extractor import EntityExtractor
            entities = EntityExtractor(use_llm_if_available=False).extract(chunk)

        if len(entities) < 2:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
        relationships: list[Relationship] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        # Compile relationship predicate cue mappings
        predicate_cues: list[tuple[re.Pattern, RelationType, str]] = [
            (re.compile(r"\b(relies\s+on|depends\s+on|delegates\s+(?:all\s+)?(?:user\s+)?authentication\s+to|requires)\b", re.IGNORECASE), RelationType.DEPENDS_ON, "relies on for operational capabilities"),
            (re.compile(r"\b(uses|utilizes|relies\s+on|powers|subscribed\s+to|operates)\b", re.IGNORECASE), RelationType.USES, "uses or consumes service/product"),
            (re.compile(r"\b(affects|impacts|breaks|deprecated|replaces)\b", re.IGNORECASE), RelationType.AFFECTS, "adversely affects or changes interface of"),
            (re.compile(r"\b(introduced\s+in|released\s+in|transitioned\s+in|rolled\s+out\s+in)\b", re.IGNORECASE), RelationType.INTRODUCED_IN, "introduced or launched in release"),
            (re.compile(r"\b(supports|provides|features|offers)\b", re.IGNORECASE), RelationType.SUPPORTS, "provides or supports capability for"),
            (re.compile(r"\b(deployed\s+(?:on|in)|hosted\s+(?:on|in)|runs\s+on)\b", re.IGNORECASE), RelationType.DEPLOYS_TO, "deploys onto infrastructure environment"),
            (re.compile(r"\b(integrates\s+with|connects\s+to|exchanges\s+with|streams\s+into)\b", re.IGNORECASE), RelationType.INTEGRATES_WITH, "exchanges data or integrates with"),
            (re.compile(r"\b(complies\s+with|satisfies|certified\s+under|audited\s+under)\b", re.IGNORECASE), RelationType.COMPLIES_WITH, "complies with regulatory policy or certification"),
            (re.compile(r"\b(governed\s+by|evaluated\s+by|regulated\s+by|enforced\s+by)\b", re.IGNORECASE), RelationType.OWNED_BY, "governed or policy-enforced by"),
        ]

        # Check each sentence for entity co-occurrences
        for sentence in sentences:
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            # Find entities present in this sentence
            present_entities = [e for e in entities if e.name.lower() in sentence_clean.lower()]
            if len(present_entities) < 2:
                continue

            # Check entity pairs in order of appearance in sentence
            for i in range(len(present_entities)):
                for j in range(len(present_entities)):
                    if i == j:
                        continue
                    src = present_entities[i]
                    tgt = present_entities[j]

                    # Match semantic predicate between src and tgt
                    rel_type, description = self._infer_relation_type(sentence_clean, src.name, tgt.name, predicate_cues)

                    pair_key = (src.name.lower(), tgt.name.lower(), rel_type.value)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    rel = self._create_relationship(
                        source_name=src.name,
                        target_name=tgt.name,
                        rel_type=rel_type,
                        description=description,
                        evidence_text=sentence_clean,
                        chunk=chunk,
                        confidence=0.90,
                    )
                    relationships.append(rel)

        return relationships

    def _infer_relation_type(
        self,
        sentence: str,
        src_name: str,
        tgt_name: str,
        cues: list[tuple[re.Pattern, RelationType, str]],
    ) -> tuple[RelationType, str]:
        """Infer relation type from sentence cues and entity types."""
        # Find positions to evaluate directionality
        src_pos = sentence.lower().find(src_name.lower())
        tgt_pos = sentence.lower().find(tgt_name.lower())

        # If source appears before target, check connecting text
        connecting_text = sentence[src_pos:tgt_pos] if src_pos < tgt_pos else sentence[tgt_pos:src_pos]

        for pattern, r_type, desc in cues:
            if pattern.search(connecting_text) or pattern.search(sentence):
                return r_type, desc

        # Domain fallback defaults
        if "customer" in src_name.lower() or "corp" in src_name.lower():
            return RelationType.USES, "Customer utilizes target solution"
        if "version" in src_name.lower():
            return RelationType.INTRODUCED_IN, "Associated with software release"

        return RelationType.RELATED_TO, "Relates to context in chunk"

    def _create_relationship(
        self,
        source_name: str,
        target_name: str,
        rel_type: RelationType,
        description: str,
        evidence_text: str,
        chunk: DocumentChunk,
        confidence: float = 1.0,
    ) -> Relationship:
        """Instantiate a validated Relationship with grounded Evidence."""
        src_slug = re.sub(r"[^a-z0-9]+", "_", source_name.lower()).strip("_")
        tgt_slug = re.sub(r"[^a-z0-9]+", "_", target_name.lower()).strip("_")
        rel_slug = rel_type.value.lower()
        rel_id = f"rel:{src_slug}:{rel_slug}:{tgt_slug}"

        evidence = Evidence(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            text=evidence_text,
            confidence=confidence,
        )

        return Relationship(
            id=rel_id,
            source_id=f"entity:{src_slug}",
            target_id=f"entity:{tgt_slug}",
            type=rel_type,
            description=description,
            weight=1.0,
            evidence=[evidence],
            metadata={"source_chunk_id": chunk.chunk_id, "document_id": chunk.document_id},
        )
