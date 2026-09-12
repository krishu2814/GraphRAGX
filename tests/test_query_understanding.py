"""Unit and integration tests for query understanding, entity linking, and retrieval planning."""

import pytest

from app.graph.neo4j_client import NetworkXGraphDriver
from app.models.entities import EntityType
from app.models.query import QueryIntent, RetrievalStrategy
from app.query.analyzer import QueryAnalyzer
from app.query.entity_linker import EntityLinker
from app.query.intent_classifier import IntentClassifier
from app.query.planner import RetrievalPlanner


class TestEntityLinker:
    """Tests for entity mention extraction, alias resolution, and greedy longest-match disambiguation."""

    def test_exact_canonical_linking(self) -> None:
        linker = EntityLinker()
        entities = linker.link_entities("Tell me about Product Nova and Identity Service.")
        assert len(entities) == 2
        names = [e.canonical_name for e in entities]
        assert "Product Nova" in names
        assert "Identity Service" in names
        assert entities[0].confidence == 1.0

    def test_alias_linking(self) -> None:
        linker = EntityLinker()
        entities = linker.link_entities("Does Acme use IdP for authentication in v3.2?")
        names = [e.canonical_name for e in entities]
        assert "Acme Corp" in names
        assert "Identity Service" in names
        assert "Version 3.2" in names

    def test_greedy_longest_match_disambiguation(self) -> None:
        linker = EntityLinker()
        # "Product Nova" should win over "Nova", preventing duplicate or partial matches
        query = "How does Product Nova handle streaming?"
        entities = linker.link_entities(query)
        assert len(entities) == 1
        assert entities[0].canonical_name == "Product Nova"
        assert entities[0].raw_mention == "Product Nova"

    def test_multiple_technical_versions_disambiguation(self) -> None:
        linker = EntityLinker()
        query = "We upgraded from OAuth 2.0 to OAuth 2.1 in Polaris release."
        entities = linker.link_entities(query)
        names = [e.canonical_name for e in entities]
        assert "OAuth 2.0" in names
        assert "OAuth 2.1" in names
        assert "Version 3.2" in names  # Polaris is an alias for Version 3.2

    def test_empty_and_no_match_query(self) -> None:
        linker = EntityLinker()
        assert linker.link_entities("") == []
        assert linker.link_entities("   ") == []
        assert linker.link_entities("What is the recipe for chocolate cake?") == []

    def test_custom_entity_registration(self) -> None:
        linker = EntityLinker()
        linker.add_entity(
            canonical_id="entity:tool:turbocache",
            canonical_name="TurboCache",
            entity_type=EntityType.TECHNOLOGY,
            aliases=["Turbo Cache", "TCache"],
        )
        entities = linker.link_entities("Does our cluster use TCache?")
        assert len(entities) == 1
        assert entities[0].canonical_id == "entity:tool:turbocache"
        assert entities[0].canonical_name == "TurboCache"

    def test_dynamic_graph_synchronization(self) -> None:
        from app.models.entities import Entity
        graph = NetworkXGraphDriver()
        graph.add_entity(
            Entity(
                id="entity:customer:wayne_enterprises",
                name="Wayne Enterprises",
                type=EntityType.CUSTOMER,
                description="Gotham technology conglomerate",
                aliases=["Wayne Corp", "Wayne Tech"],
            )
        )
        linker = EntityLinker(graph_client=graph)
        entities = linker.link_entities("Check contracts for Wayne Tech.")
        assert len(entities) == 1
        assert entities[0].canonical_id == "entity:customer:wayne_enterprises"
        assert entities[0].canonical_name == "Wayne Enterprises"


class TestIntentClassifier:
    """Tests for heuristic and rule-based query intent classification."""

    def setup_method(self) -> None:
        self.classifier = IntentClassifier()
        self.linker = EntityLinker()

    def test_direct_fact_classification(self) -> None:
        q1 = "What is the price of the Developer Plan?"
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.DIRECT_FACT

        q2 = "What is the rate limit for free tier?"
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.DIRECT_FACT

    def test_entity_lookup_classification(self) -> None:
        q1 = "What is Product Nova?"
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.ENTITY_LOOKUP

        q2 = "Tell me about Identity Service."
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.ENTITY_LOOKUP

    def test_relationship_classification(self) -> None:
        q1 = "How does Acme Corp depend on Identity Service?"
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.RELATIONSHIP

        q2 = "Does Initech connect to Gateway Service?"
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.RELATIONSHIP

    def test_multi_hop_classification(self) -> None:
        q1 = "How does an incident in Identity Service indirectly affect Acme Corp?"
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.MULTI_HOP

        q2 = "Trace the path from Initech to OAuth 2.1."
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.MULTI_HOP

    def test_comparison_classification(self) -> None:
        q1 = "Compare Product Nova and Product Orion."
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.COMPARISON

        q2 = "What is the difference between OAuth 2.0 and OAuth 2.1?"
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.COMPARISON

    def test_global_classification(self) -> None:
        q1 = "Give me an overview of all platform products."
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.GLOBAL

        q2 = "List all services across the entire platform."
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.GLOBAL

    def test_no_answer_classification(self) -> None:
        q1 = "What is the capital of France?"
        assert self.classifier.classify(q1, self.linker.link_entities(q1)) == QueryIntent.NO_ANSWER

        q2 = "Who directed the movie Inception?"
        assert self.classifier.classify(q2, self.linker.link_entities(q2)) == QueryIntent.NO_ANSWER


class TestRetrievalPlanner:
    """Tests for mapping intent, entities, and constraints into execution plans."""

    def setup_method(self) -> None:
        self.planner = RetrievalPlanner()
        self.linker = EntityLinker()

    def test_relationship_plan(self) -> None:
        query = "How does Acme Corp depend on Identity Service?"
        entities = self.linker.link_entities(query)
        plan = self.planner.plan(query=query, intent=QueryIntent.RELATIONSHIP, linked_entities=entities)

        assert plan.strategy == RetrievalStrategy.MULTI_HOP
        assert plan.max_hops == 2
        assert plan.require_paths is True
        assert len(plan.seed_entities) == 2

    def test_comparison_plan(self) -> None:
        query = "Compare Product Nova and Product Orion"
        entities = self.linker.link_entities(query)
        plan = self.planner.plan(query=query, intent=QueryIntent.COMPARISON, linked_entities=entities)

        assert plan.strategy == RetrievalStrategy.HYBRID
        assert plan.require_paths is True
        assert plan.top_k == 8

    def test_global_plan(self) -> None:
        query = "Summarize all services in CloudScale"
        plan = self.planner.plan(query=query, intent=QueryIntent.GLOBAL, linked_entities=[])

        assert plan.strategy == RetrievalStrategy.GLOBAL
        assert plan.require_paths is False
        assert plan.top_k == 10
        assert EntityType.SERVICE in plan.target_entity_types

    def test_metadata_filters_extraction(self) -> None:
        query = "Find confidential documents in engineering team for version 3.2"
        plan = self.planner.plan(query=query, intent=QueryIntent.DIRECT_FACT, linked_entities=[])

        assert plan.filters.get("version") == "3.2"
        assert plan.filters.get("access_tier") == "Confidential"
        assert plan.filters.get("department") == "Engineering"


class TestQueryAnalyzerIntegration:
    """End-to-end integration tests for QueryAnalyzer."""

    def test_end_to_end_analysis(self) -> None:
        analyzer = QueryAnalyzer()
        plan = analyzer.analyze("How does Acme Corp depend on Identity Service in version 3.2?")

        assert plan.intent == QueryIntent.RELATIONSHIP
        assert plan.strategy == RetrievalStrategy.MULTI_HOP
        assert plan.require_paths is True
        assert plan.filters.get("version") == "3.2"
        canonical_names = [e.canonical_name for e in plan.seed_entities]
        assert "Acme Corp" in canonical_names
        assert "Identity Service" in canonical_names

    def test_out_of_domain_query_handling(self) -> None:
        analyzer = QueryAnalyzer()
        plan = analyzer.analyze("How many miles is it to the moon?")

        assert plan.intent == QueryIntent.NO_ANSWER
        assert plan.strategy == RetrievalStrategy.VECTOR
        assert plan.top_k == 1
        assert len(plan.seed_entities) == 0
