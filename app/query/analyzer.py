"""High-level QueryAnalyzer facade coordinating entity linking, intent classification, and retrieval planning."""

import logging

from app.graph.neo4j_client import GraphClient
from app.models.query import RetrievalPlan
from app.query.entity_linker import EntityLinker
from app.query.intent_classifier import IntentClassifier
from app.query.planner import RetrievalPlanner

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Orchestrates query understanding, entity linking, intent classification, and planning."""

    def __init__(
        self,
        linker: EntityLinker | None = None,
        classifier: IntentClassifier | None = None,
        planner: RetrievalPlanner | None = None,
        graph_client: GraphClient | None = None,
        use_llm: bool = False,
    ) -> None:
        self.linker = linker or EntityLinker(graph_client=graph_client)
        self.classifier = classifier or IntentClassifier(use_llm=use_llm)
        self.planner = planner or RetrievalPlanner()

    def analyze(self, query: str) -> RetrievalPlan:
        """Run complete query analysis pipeline and return a structured RetrievalPlan."""
        # 1. Link entity mentions to canonical knowledge graph entities
        linked_entities = self.linker.link_entities(query)

        # 2. Classify user intent
        intent = self.classifier.classify(query, linked_entities=linked_entities)

        # 3. Formulate retrieval execution plan
        plan = self.planner.plan(
            query=query,
            intent=intent,
            linked_entities=linked_entities,
        )

        logger.debug(
            f"Query analyzed: '{query}' -> intent={plan.intent.value}, "
            f"strategy={plan.strategy.value}, entities={[e.canonical_name for e in plan.seed_entities]}"
        )
        return plan
