"""Query intent classification engine for GraphRAGX."""

import logging
import re
from typing import Any

from app.config import get_settings
from app.models.query import LinkedEntity, QueryIntent

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifies user queries into discrete intent categories guiding retrieval strategy."""

    # Keywords indicating out-of-scope or unanswerable queries
    DOMAIN_KEYWORDS = {
        "product", "products", "service", "services", "tier", "tiers", "plan", "plans",
        "pricing", "cost", "costs", "auth", "token", "tokens", "oauth", "incident",
        "incidents", "outage", "outages", "compliance", "policy", "policies", "gdpr",
        "soc2", "customer", "customers", "cluster", "clusters", "broker", "brokers",
        "gateway", "gateways", "version", "versions", "release", "releases", "api", "apis",
        "cloudscale", "database", "databases", "analytics", "stream", "streaming",
        "pipeline", "pipelines", "sla", "rbac", "abac", "encryption", "latency",
        "throughput", "endpoint", "endpoints", "architecture", "support", "license",
        "storage", "retention", "rate", "limit", "limits", "nova", "orion", "atlas",
        "vega", "acme", "globex", "initech", "envoy", "kafka", "redis", "arrow",
        "audit", "audits", "security", "failover", "ingress", "egress", "platform",
        "platforms", "system", "systems", "catalog", "overview", "summary",
    }

    # Comparison patterns
    COMPARISON_PATTERNS = [
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bdifference\s+between\b",
        r"\bdiffer(?:s)?\s+from\b",
        r"\bversus\b",
        r"\bvs\.?\b",
        r"\bbetter\s+than\b",
        r"\bpros\s+and\s+cons\b",
        r"\btrade(?:-)?offs?\b",
    ]

    # Global / holistic patterns
    GLOBAL_PATTERNS = [
        r"\ball\s+(?:products|services|customers|policies|incidents|plans|tiers)\b",
        r"\blist\s+all\b",
        r"\bsummarize\s+all\b",
        r"\boverview\s+of\s+all\b",
        r"\bentire\s+(?:platform|system|catalog|ecosystem|portfolio)\b",
        r"\bacross\s+(?:all|the\s+platform|the\s+entire)\b",
        r"\bevery\s+(?:product|service|customer|incident)\b",
        r"\bwhat\s+(?:products|services|plans)\s+(?:exist|are\s+available|do\s+we\s+offer)\b",
    ]

    # Multi-hop patterns
    MULTI_HOP_PATTERNS = [
        r"\bindirect(?:ly)?\b",
        r"\bchain\b",
        r"\bpath\s+(?:from|between)\b",
        r"\btrace\s+(?:the\s+path|dependencies)\b",
        r"\bimpact\s+of\s+.+\s+on\b",
        r"\baffect(?:s)?\b",
        r"\bcascade\b",
        r"\bdownstream\b",
        r"\bupstream\b",
        r"\bblast\s+radius\b",
        r"\bdepend(?:s)?\s+on\s+.+\s+that\b",
    ]

    # Fact lookup patterns (specific numeric, parameter, or SLA values)
    FACT_PATTERNS = [
        r"\bhow\s+much\b",
        r"\bwhat\s+is\s+the\s+(?:price|cost|rate\s+limit|port|sla|quota|timeout|fee|retention)\b",
        r"\bhow\s+many\b",
        r"\bwhich\s+port\b",
        r"\bcost\s+of\b",
        r"\bpricing\s+for\b",
        r"\bthroughput\s+limit\b",
    ]

    # Relationship patterns
    RELATIONSHIP_PATTERNS = [
        r"\bconnect(?:ed)?\s+to\b",
        r"\brelationship\s+between\b",
        r"\bdepend(?:s)?\s+on\b",
        r"\buse(?:s|d)?\s+by\b",
        r"\bdoes\s+.+\s+use\b",
        r"\bintegrate(?:s|d)?\s+with\b",
        r"\binteract(?:s)?\s+with\b",
        r"\brelate(?:s|d)?\s+to\b",
        r"\blinked\s+to\b",
    ]

    # Entity lookup patterns
    ENTITY_LOOKUP_PATTERNS = [
        r"^what\s+is\b",
        r"^tell\s+me\s+about\b",
        r"^describe\b",
        r"^explain\b",
        r"^overview\s+of\b",
        r"^who\s+is\b",
        r"^what\s+does\s+.+\s+do\b",
        r"^summary\s+of\b",
    ]

    def __init__(self, use_llm: bool = False) -> None:
        self.use_llm = use_llm
        self.settings = get_settings()

    def classify(self, query: str, linked_entities: list[LinkedEntity] | None = None) -> QueryIntent:
        """Classify query into a QueryIntent using rules and optional LLM refinement."""
        clean_query = query.strip()
        if not clean_query:
            return QueryIntent.NO_ANSWER

        entities = linked_entities or []

        # If LLM classification requested and API key is available, attempt structured LLM completion
        if self.use_llm and self.settings.openai_api_key:
            try:
                llm_intent = self._classify_with_llm(clean_query, entities)
                if llm_intent:
                    return llm_intent
            except Exception as e:
                logger.warning(f"LLM classification failed ({e}), falling back to deterministic heuristic.")

        # Default deterministic classification
        return self._classify_heuristically(clean_query, entities)

    def _classify_heuristically(self, query: str, entities: list[LinkedEntity]) -> QueryIntent:
        """Rule-based, zero-latency query intent classifier."""
        q_lower = query.lower()

        # 1. Out-of-domain check (NO_ANSWER)
        tokens = set(re.findall(r"\b[a-zA-Z0-9_-]+\b", q_lower))
        has_domain_term = bool(tokens & self.DOMAIN_KEYWORDS)
        if not entities and not has_domain_term:
            return QueryIntent.NO_ANSWER

        # 2. Comparison intent
        for pattern in self.COMPARISON_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.COMPARISON
        # If query has 2+ entities and asking "or", "vs", or comparison words
        if len(entities) >= 2 and re.search(r"\b(?:or|versus|difference)\b", q_lower):
            return QueryIntent.COMPARISON

        # 3. Global / holistic intent
        for pattern in self.GLOBAL_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.GLOBAL

        # 4. Multi-hop intent
        for pattern in self.MULTI_HOP_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.MULTI_HOP

        # 5. Direct Fact lookup
        for pattern in self.FACT_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.DIRECT_FACT

        # 6. Relationship intent
        for pattern in self.RELATIONSHIP_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.RELATIONSHIP
        # If query mentions 2 distinct entities and is asking about their connection
        if len(entities) >= 2:
            return QueryIntent.RELATIONSHIP

        # 7. Entity Lookup intent
        for pattern in self.ENTITY_LOOKUP_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryIntent.ENTITY_LOOKUP
        if len(entities) == 1 and (
            q_lower.startswith("what")
            or q_lower.startswith("who")
            or "overview" in q_lower
            or "describe" in q_lower
            or "tell me" in q_lower
        ):
            return QueryIntent.ENTITY_LOOKUP

        # Fallback heuristic:
        # If an entity was linked, treat as entity lookup or fact depending on length
        if len(entities) == 1:
            return QueryIntent.ENTITY_LOOKUP
        elif has_domain_term:
            return QueryIntent.DIRECT_FACT

        return QueryIntent.NO_ANSWER

    def _classify_with_llm(self, query: str, entities: list[LinkedEntity]) -> QueryIntent | None:
        """Optional OpenAI LLM classification for ambiguous natural language queries."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.openai_api_key)
            entity_str = ", ".join(f"{e.canonical_name} ({e.entity_type})" for e in entities) or "None"

            prompt = (
                f"You are a query intent classifier for GraphRAGX enterprise search.\n"
                f"User Query: '{query}'\n"
                f"Detected Entities: {entity_str}\n\n"
                f"Classify the query into exactly one of these intents:\n"
                f"- DIRECT_FACT: Simple lookup of specific factual detail, metric, or price\n"
                f"- ENTITY_LOOKUP: Summarize or describe a specific entity\n"
                f"- RELATIONSHIP: Connection between two entities\n"
                f"- MULTI_HOP: Indirect or chained relational query across multiple intermediate nodes\n"
                f"- GLOBAL: Holistic summary across the entire platform or all entities\n"
                f"- COMPARISON: Compare two entities, products, versions, or plans\n"
                f"- NO_ANSWER: Out of domain or unverifiable question\n\n"
                f"Return ONLY the intent name in all caps."
            )
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20,
            )
            content = response.choices[0].message.content
            if content:
                clean_res = content.strip().upper()
                for intent in QueryIntent:
                    if intent.value == clean_res:
                        return intent
        except Exception as e:
            logger.debug(f"LLM classification exception: {e}")
        return None
