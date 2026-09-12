#!/usr/bin/env python3
"""CLI utility to test query understanding, intent classification, and retrieval planning."""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.graph.neo4j_client import get_graph_client
from app.query.analyzer import QueryAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAGX Query Analysis CLI")
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="User query to analyze (e.g. 'How does Acme Corp depend on Identity Service?')",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use OpenAI model for intent classification if API key is available",
    )
    args = parser.parse_args()

    # Optional graph client for dynamic entity synchronization
    client = None
    try:
        client = get_graph_client()
    except Exception:
        pass

    analyzer = QueryAnalyzer(graph_client=client, use_llm=args.use_llm)
    plan = analyzer.analyze(args.query)

    print("\n" + "=" * 55)
    print(" GraphRAGX — Query Understanding & Retrieval Plan")
    print("=" * 55)
    print(f" Query:             {plan.query}")
    print(f" Classified Intent: {plan.intent.value}")
    print(f" Strategy:          {plan.strategy.value}")
    print(f" Max Graph Hops:    {plan.max_hops}")
    print(f" Require Paths:     {plan.require_paths}")
    print(f" Desired Top K:     {plan.top_k}")

    if plan.filters:
        print("\n Metadata Filters:")
        for key, val in plan.filters.items():
            print(f"   • {key}: {val}")

    if plan.target_entity_types:
        print("\n Target Entity Types:")
        for et in plan.target_entity_types:
            print(f"   • {et.value}")

    print(f"\n Linked Entities ({len(plan.seed_entities)}):")
    if plan.seed_entities:
        for idx, ent in enumerate(plan.seed_entities, start=1):
            print(f"   {idx}. Mention:     '{ent.raw_mention}'")
            print(f"      Canonical:   {ent.canonical_name} ({ent.canonical_id})")
            print(f"      Type:        {ent.entity_type.value}")
            print(f"      Confidence:  {ent.confidence:.2f}")
    else:
        print("   (No specific entities detected in query)")

    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
