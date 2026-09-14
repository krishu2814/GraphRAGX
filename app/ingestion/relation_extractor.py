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
            (re.compile(r"\b(uses|utilizes|powers|subscribed\s+to|operates|contracts?\s+for)\b", re.IGNORECASE), RelationType.USES, "uses or consumes service/product"),
            (re.compile(r"\b(affects|impacts|breaks|deprecated|replaces)\b", re.IGNORECASE), RelationType.AFFECTS, "adversely affects or changes interface of"),
            (re.compile(r"\b(introduced\s+in|released\s+in|transitioned\s+(?:in|to)|rolled\s+out\s+in|upgraded\s+to)\b", re.IGNORECASE), RelationType.INTRODUCED_IN, "introduced or launched in release"),
            (re.compile(r"\b(supports|provides|features|offers|enforces|implements)\b", re.IGNORECASE), RelationType.SUPPORTS, "provides or supports capability for"),
            (re.compile(r"\b(deployed\s+(?:on|in)|hosted\s+(?:on|in)|runs\s+on)\b", re.IGNORECASE), RelationType.DEPLOYS_TO, "deploys onto infrastructure environment"),
            (re.compile(r"\b(integrates\s+with|connects\s+to|exchanges\s+with|streams\s+into)\b", re.IGNORECASE), RelationType.INTEGRATES_WITH, "exchanges data or integrates with"),
            (re.compile(r"\b(complies\s+with|satisfies|certified\s+under|audited\s+under)\b", re.IGNORECASE), RelationType.COMPLIES_WITH, "complies with regulatory policy or certification"),
            (re.compile(r"\b(governed\s+by|evaluated\s+by|regulated\s+by|enforced\s+by)\b", re.IGNORECASE), RelationType.OWNED_BY, "governed or policy-enforced by"),
            (re.compile(r"\b(part\s+of|component\s+of|subsystem\s+of|module\s+of)\b", re.IGNORECASE), RelationType.PART_OF, "part or component of"),
        ]

        # Check each sentence for entity co-occurrences
        for sentence in sentences:
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            # Find entities present in this sentence using boundary matching
            matches: list[tuple[Entity, int, int]] = []
            for e in entities:
                pattern = re.compile(r"(?<![a-zA-Z0-9])" + re.escape(e.name) + r"(?![a-zA-Z0-9])", re.IGNORECASE)
                for m in pattern.finditer(sentence_clean):
                    matches.append((e, m.start(), m.end()))

            # Filter overlapping spans (prefer longer entity matches)
            matches.sort(key=lambda x: (x[1], -(x[2] - x[1])))
            filtered: list[tuple[Entity, int, int]] = []
            last_end = -1
            for e, start, end in matches:
                if start >= last_end:
                    filtered.append((e, start, end))
                    last_end = end

            if len(filtered) < 2:
                continue

            # Evaluate ordered entity pairs where src appears before tgt in the sentence
            for i in range(len(filtered)):
                for j in range(i + 1, len(filtered)):
                    src, s_start, s_end = filtered[i]
                    tgt, t_start, t_end = filtered[j]

                    if src.name.lower() == tgt.name.lower():
                        continue

                    # If non-adjacent, ensure intermediate entity does not have its own predicate
                    has_intermediate_predicate = False
                    for k in range(i + 1, j):
                        _, _, k_end = filtered[k]
                        k_between = sentence_clean[k_end:t_start]
                        if any(pat.search(k_between) for pat, _, _ in predicate_cues):
                            has_intermediate_predicate = True
                            break
                    if has_intermediate_predicate:
                        continue

                    connecting_text = sentence_clean[s_end:t_start]
                    rel_type: RelationType | None = None
                    description = ""

                    for pattern, r_type, desc in predicate_cues:
                        if pattern.search(connecting_text):
                            rel_type = r_type
                            description = desc
                            break

                    if rel_type is None and j == i + 1:
                        # Fallback only for adjacent co-occurring pairs
                        if "customer" in src.name.lower() or "corp" in src.name.lower():
                            rel_type = RelationType.USES
                            description = "Customer utilizes target solution"
                        elif "version" in tgt.name.lower():
                            rel_type = RelationType.INTRODUCED_IN
                            description = "Associated with software release"
                        else:
                            rel_type = RelationType.RELATED_TO
                            description = "Relates to context in chunk"

                    if rel_type is None:
                        continue

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
        src_m = re.search(r"(?<![a-zA-Z0-9])" + re.escape(src_name) + r"(?![a-zA-Z0-9])", sentence, re.IGNORECASE)
        tgt_m = re.search(r"(?<![a-zA-Z0-9])" + re.escape(tgt_name) + r"(?![a-zA-Z0-9])", sentence, re.IGNORECASE)

        src_pos = src_m.start() if src_m else sentence.lower().find(src_name.lower())
        tgt_pos = tgt_m.start() if tgt_m else sentence.lower().find(tgt_name.lower())
        src_end = src_m.end() if src_m else (src_pos + len(src_name))
        tgt_end = tgt_m.end() if tgt_m else (tgt_pos + len(tgt_name))

        # Check connecting text between source and target
        if src_pos < tgt_pos:
            connecting_text = sentence[src_end:tgt_pos]
            for pattern, r_type, desc in cues:
                if pattern.search(connecting_text):
                    return r_type, desc
        elif tgt_pos < src_pos:
            connecting_text = sentence[tgt_end:src_pos]
            for pattern, r_type, desc in cues:
                if pattern.search(connecting_text):
                    return r_type, desc

        # Domain fallback defaults
        if "customer" in src_name.lower() or "corp" in src_name.lower():
            return RelationType.USES, "Customer utilizes target solution"
        if "version" in tgt_name.lower():
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
