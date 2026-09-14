"""Retrieval planner mapping user queries, intents, and linked entities into execution plans."""

import logging
import re
from typing import Any

from app.models.entities import EntityType
from app.models.query import LinkedEntity, QueryIntent, RetrievalPlan, RetrievalStrategy

logger = logging.getLogger(__name__)


class RetrievalPlanner:
    """Generates execution plans specifying retrieval strategy, traversal depth, and metadata filters."""

    # Keywords mapping to target entity types
    TARGET_TYPE_PATTERNS: list[tuple[list[str], EntityType]] = [
        (["customer", "customers", "client", "clients", "subscriber", "subscribers", "tenant"], EntityType.CUSTOMER),
        (["service", "services", "microservice", "microservices", "api"], EntityType.SERVICE),
        (["product", "products", "platform", "platforms", "app", "apps"], EntityType.PRODUCT),
        (["policy", "policies", "compliance", "regulation", "standard", "audit"], EntityType.POLICY),
        (["incident", "incidents", "outage", "outages", "postmortem", "downtime"], EntityType.INCIDENT),
        (["technology", "technologies", "tech", "broker", "database", "cache"], EntityType.TECHNOLOGY),
        (["version", "versions", "release", "releases"], EntityType.VERSION),
        (["plan", "plans", "tier", "tiers", "subscription"], EntityType.PLAN),
    ]

    DEPARTMENTS = ["engineering", "security", "legal", "finance", "compliance", "product"]
    ACCESS_TIERS = ["public", "internal", "confidential", "restricted"]

    def plan(
        self,
        query: str,
        intent: QueryIntent,
        linked_entities: list[LinkedEntity] | None = None,
    ) -> RetrievalPlan:
        """Construct a structured RetrievalPlan from query, intent, and linked entities."""
        entities = linked_entities or []
        filters = self._extract_metadata_filters(query)
        target_types = self._infer_target_entity_types(query)

        strategy = self._determine_strategy(intent, entities)
        max_hops = self._determine_max_hops(intent, query)
        require_paths = self._determine_require_paths(intent)
        top_k = self._determine_top_k(intent)

        return RetrievalPlan(
            query=query,
            intent=intent,
            strategy=strategy,
            seed_entities=entities,
            target_entity_types=target_types,
            max_hops=max_hops,
            require_paths=require_paths,
            top_k=top_k,
            filters=filters,
        )

    def _determine_strategy(self, intent: QueryIntent, entities: list[LinkedEntity]) -> RetrievalStrategy:
        """Map QueryIntent to candidate RetrievalStrategy."""
        if intent == QueryIntent.GLOBAL:
            return RetrievalStrategy.GLOBAL

        if intent == QueryIntent.MULTI_HOP:
            return RetrievalStrategy.MULTI_HOP

        if intent == QueryIntent.RELATIONSHIP:
            # If two or more entities are known, use multi-hop path retrieval
            return RetrievalStrategy.MULTI_HOP

        if intent == QueryIntent.COMPARISON:
            # Comparing entities benefits from hybrid retrieval
            return RetrievalStrategy.HYBRID

        if intent == QueryIntent.ENTITY_LOOKUP:
            # Entity overview uses hybrid (vector text chunks + graph 1-hop facts)
            return RetrievalStrategy.HYBRID

        if intent == QueryIntent.DIRECT_FACT:
            # If an entity is specified, hybrid lookup can grab both table/chunk and graph node
            if entities:
                return RetrievalStrategy.HYBRID
            return RetrievalStrategy.VECTOR

        # Fallback for NO_ANSWER or generic queries
        return RetrievalStrategy.VECTOR

    def _determine_max_hops(self, intent: QueryIntent, query: str) -> int:
        """Determine maximum graph traversal depth based on intent and query hints."""
        q_lower = query.lower()

        if intent == QueryIntent.MULTI_HOP:
            if "3 hops" in q_lower or "three hops" in q_lower or "chain" in q_lower:
                return 3
            return 2

        if intent in (QueryIntent.RELATIONSHIP, QueryIntent.COMPARISON):
            return 2

        # 1 hop is sufficient for entity lookup, direct fact, and global
        return 1

    def _determine_require_paths(self, intent: QueryIntent) -> bool:
        """Flag whether explicit graph explanation paths are required for generation."""
        return intent in (QueryIntent.MULTI_HOP, QueryIntent.RELATIONSHIP, QueryIntent.COMPARISON)

    def _determine_top_k(self, intent: QueryIntent) -> int:
        """Set number of evidence chunks required according to query breadth."""
        if intent == QueryIntent.GLOBAL:
            return 10
        if intent == QueryIntent.COMPARISON:
            return 8
        if intent == QueryIntent.MULTI_HOP:
            return 6
        if intent in (QueryIntent.ENTITY_LOOKUP, QueryIntent.RELATIONSHIP):
            return 5
        if intent == QueryIntent.DIRECT_FACT:
            return 3
        return 1

    def _infer_target_entity_types(self, query: str) -> list[EntityType]:
        """Detect what kind of entities the query is asking to discover."""
        q_lower = query.lower()
        target_types: list[EntityType] = []

        for keywords, entity_type in self.TARGET_TYPE_PATTERNS:
            for kw in keywords:
                # Check for whole-word matches
                if re.search(rf"\b{re.escape(kw)}\b", q_lower):
                    if entity_type not in target_types:
                        target_types.append(entity_type)
                    break

        return target_types

    def _extract_metadata_filters(self, query: str) -> dict[str, Any]:
        """Extract document metadata filters (version, tier, department) from query text."""
        filters: dict[str, Any] = {}
        q_lower = query.lower()

        # Version filter: e.g. "version 3.2", "v3.2", "3.2"
        version_match = re.search(r"\b(?:version\s+|v)?(3\.[12])\b", q_lower)
        if version_match:
            filters["version"] = version_match.group(1)

        # Access Tier filter: require context like "confidential tier/documents" or "tier: confidential"
        tier_match = (
            re.search(r"\b(?:access\s+tier|tier|classification)\s*[:=]?\s*(public|internal|confidential|restricted)\b", q_lower)
            or re.search(r"\b(public|internal|confidential|restricted)\s+(?:tier|access|classification|documents?|docs?)\b", q_lower)
        )
        if tier_match:
            filters["access_tier"] = tier_match.group(1).capitalize()
        elif "confidential" in q_lower:
            filters["access_tier"] = "Confidential"
        elif "restricted" in q_lower:
            filters["access_tier"] = "Restricted"

        # Department filter: require context like "in engineering", "security department", "legal team"
        dept_match = re.search(
            r"\b(?:in|from|department|dept|team)\s+(?:the\s+)?(engineering|security|legal|finance|compliance|infrastructure|governance)\b",
            q_lower,
        )
        if dept_match:
            filters["department"] = dept_match.group(1).capitalize()
        else:
            dept_suffix_match = re.search(
                r"\b(engineering|security|legal|finance|compliance|infrastructure|governance)\s+(?:department|team|docs?|documents?)\b",
                q_lower,
            )
            if dept_suffix_match:
                filters["department"] = dept_suffix_match.group(1).capitalize()

        return filters
