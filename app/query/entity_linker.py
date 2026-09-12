"""Entity linking and mention disambiguation for GraphRAGX."""

import logging
import re
from typing import Any

from app.graph.neo4j_client import GraphClient, NetworkXGraphDriver, Neo4jGraphDriver
from app.ingestion.entity_resolution import EntityResolver
from app.models.entities import EntityType
from app.models.query import LinkedEntity

logger = logging.getLogger(__name__)


class EntityLinker:
    """Links entity mentions in user queries to canonical knowledge graph entities."""

    # Additional standard domain entities known across documents
    STANDARD_ENTITIES: list[dict[str, Any]] = [
        {
            "canonical_id": "entity:plan:developer",
            "canonical_name": "Developer Plan",
            "type": EntityType.PLAN,
            "description": "Entry-level free tier for prototyping and individual developers",
            "aliases": ["Developer Plan", "Free Tier", "Developer Tier", "Free Plan"],
        },
        {
            "canonical_id": "entity:plan:pro",
            "canonical_name": "Pro Plan",
            "type": EntityType.PLAN,
            "description": "Standard business plan with 99.9% SLA and dedicated support",
            "aliases": ["Pro Plan", "Pro Tier", "Professional Plan"],
        },
        {
            "canonical_id": "entity:plan:enterprise",
            "canonical_name": "Enterprise Plan",
            "type": EntityType.PLAN,
            "description": "Mission-critical custom enterprise plan with 99.99% SLA and HIPAA/SOC2",
            "aliases": ["Enterprise Plan", "Enterprise Tier", "Custom Tier"],
        },
        {
            "canonical_id": "entity:technology:kafka",
            "canonical_name": "Apache Kafka",
            "type": EntityType.TECHNOLOGY,
            "description": "Distributed streaming event bus backing Product Orion",
            "aliases": ["Apache Kafka", "Kafka", "Kafka Cluster"],
        },
        {
            "canonical_id": "entity:technology:arrow",
            "canonical_name": "Apache Arrow",
            "type": EntityType.TECHNOLOGY,
            "description": "In-memory columnar data format used for Nova analytics caching",
            "aliases": ["Apache Arrow", "Arrow", "Arrow Format"],
        },
        {
            "canonical_id": "entity:technology:redis",
            "canonical_name": "Redis",
            "type": EntityType.TECHNOLOGY,
            "description": "In-memory key-value cache used for session and token management",
            "aliases": ["Redis", "Redis Cache"],
        },
        {
            "canonical_id": "entity:technology:envoy",
            "canonical_name": "Envoy Proxy",
            "type": EntityType.TECHNOLOGY,
            "description": "High-performance edge proxy underpinning Gateway Service",
            "aliases": ["Envoy", "Envoy Proxy"],
        },
    ]

    def __init__(self, graph_client: GraphClient | None = None) -> None:
        self.graph_client = graph_client
        # Maps surface phrase (lowercase) -> candidate entity dict
        self._phrase_to_entity: dict[str, dict[str, Any]] = {}
        # Maps canonical ID -> canonical entity dict
        self._canonical_entities: dict[str, dict[str, Any]] = {}

        self._load_knowledge_base()
        if self.graph_client:
            self._load_from_graph(self.graph_client)

    def _load_knowledge_base(self) -> None:
        """Load curated canonical clusters and standard entities."""
        # 1. Curated clusters from EntityResolver
        for cluster in EntityResolver.CANONICAL_CLUSTERS:
            self.add_entity(
                canonical_id=cluster["canonical_id"],
                canonical_name=cluster["canonical_name"],
                entity_type=cluster["type"],
                aliases=cluster.get("aliases", []),
                description=cluster.get("description", ""),
            )

        # 2. Supplementary domain entities
        for item in self.STANDARD_ENTITIES:
            self.add_entity(
                canonical_id=item["canonical_id"],
                canonical_name=item["canonical_name"],
                entity_type=item["type"],
                aliases=item.get("aliases", []),
                description=item.get("description", ""),
            )

    def _load_from_graph(self, graph_client: GraphClient) -> None:
        """Dynamically synchronize entities from active graph database."""
        try:
            if isinstance(graph_client, NetworkXGraphDriver):
                for node_id, data in graph_client.graph.nodes(data=True):
                    if data.get("label") == "Entity":
                        aliases = data.get("aliases", [])
                        if isinstance(aliases, str):
                            aliases = [aliases]
                        self.add_entity(
                            canonical_id=data.get("id", node_id),
                            canonical_name=data.get("name", node_id),
                            entity_type=EntityType(data.get("type", "OTHER")),
                            aliases=aliases,
                            description=data.get("description", ""),
                        )
            elif isinstance(graph_client, Neo4jGraphDriver):
                with graph_client.driver.session(database=graph_client.database) as session:
                    res = session.run(
                        "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.type AS type, "
                        "e.aliases AS aliases, e.description AS description"
                    )
                    for record in res:
                        aliases = record["aliases"] or []
                        if isinstance(aliases, str):
                            aliases = [aliases]
                        self.add_entity(
                            canonical_id=record["id"],
                            canonical_name=record["name"],
                            entity_type=EntityType(record["type"] or "OTHER"),
                            aliases=aliases,
                            description=record["description"] or "",
                        )
        except Exception as e:
            logger.warning(f"Failed to synchronize entities from graph client: {e}")

    def add_entity(
        self,
        canonical_id: str,
        canonical_name: str,
        entity_type: EntityType,
        aliases: list[str] | None = None,
        description: str = "",
    ) -> None:
        """Register a canonical entity and its alias surface forms."""
        entity_info = {
            "canonical_id": canonical_id,
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "description": description,
        }
        self._canonical_entities[canonical_id] = entity_info

        # Index canonical name
        name_key = canonical_name.strip().lower()
        if name_key:
            self._phrase_to_entity[name_key] = {**entity_info, "is_canonical": True}

        # Index aliases
        for alias in aliases or []:
            alias_key = alias.strip().lower()
            if alias_key and alias_key not in self._phrase_to_entity:
                self._phrase_to_entity[alias_key] = {**entity_info, "is_canonical": False}

        # Also register direct canonical ID (e.g. entity:product:nova)
        self._phrase_to_entity[canonical_id.lower()] = {**entity_info, "is_canonical": True}

    def get_canonical_entity(self, identifier: str) -> LinkedEntity | None:
        """Direct lookup of an entity by ID or exact canonical name."""
        clean_id = identifier.strip().lower()
        # Direct ID
        if identifier in self._canonical_entities:
            info = self._canonical_entities[identifier]
            return LinkedEntity(
                raw_mention=identifier,
                canonical_id=info["canonical_id"],
                canonical_name=info["canonical_name"],
                entity_type=info["entity_type"],
                confidence=1.0,
            )
        # Direct name/alias
        if clean_id in self._phrase_to_entity:
            info = self._phrase_to_entity[clean_id]
            return LinkedEntity(
                raw_mention=identifier,
                canonical_id=info["canonical_id"],
                canonical_name=info["canonical_name"],
                entity_type=info["entity_type"],
                confidence=1.0 if info.get("is_canonical") else 0.95,
            )
        return None

    def link_entities(self, query: str) -> list[LinkedEntity]:
        """Extract and link entity mentions in query using greedy longest-match disambiguation."""
        if not query or not query.strip():
            return []

        # Sort candidate phrases by length descending (longest match wins)
        sorted_phrases = sorted(self._phrase_to_entity.keys(), key=lambda p: len(p), reverse=True)

        matched_spans: list[tuple[int, int]] = []
        linked_entities: list[tuple[int, LinkedEntity]] = []
        seen_canonical_ids: set[str] = set()

        for phrase in sorted_phrases:
            # Skip very short words (less than 2 chars) unless it's a version number
            if len(phrase) < 2:
                continue

            # Build regex with boundary checks
            # Use (?<![a-zA-Z0-9]) and (?![a-zA-Z0-9]) for clean token boundaries
            pattern_str = r"(?<![a-zA-Z0-9])" + re.escape(phrase) + r"(?![a-zA-Z0-9])"
            # Support flexible whitespace within multi-word phrases
            pattern_str = re.sub(r"\\ ", r"\\s+", pattern_str)

            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
            except re.error:
                continue

            for match in pattern.finditer(query):
                start, end = match.start(), match.end()

                # Check for overlap with already accepted longer spans
                is_overlapping = any(
                    not (end <= existing_start or start >= existing_end)
                    for existing_start, existing_end in matched_spans
                )

                if is_overlapping:
                    continue

                entity_info = self._phrase_to_entity[phrase]
                canonical_id = entity_info["canonical_id"]

                # Avoid duplicate linked entity objects for the same entity in the same query
                if canonical_id in seen_canonical_ids:
                    # Still record span to prevent shorter sub-terms from matching
                    matched_spans.append((start, end))
                    continue

                matched_spans.append((start, end))
                seen_canonical_ids.add(canonical_id)

                raw_mention = query[start:end]
                confidence = 1.0 if entity_info.get("is_canonical") else 0.95

                linked_entities.append((
                    start,
                    LinkedEntity(
                        raw_mention=raw_mention,
                        canonical_id=canonical_id,
                        canonical_name=entity_info["canonical_name"],
                        entity_type=entity_info["entity_type"],
                        confidence=confidence,
                    )
                ))

        # Sort linked entities by order of appearance in the original query
        linked_entities.sort(key=lambda item: item[0])
        return [entity for _, entity in linked_entities]
