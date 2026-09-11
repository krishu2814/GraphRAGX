#!/usr/bin/env python3
"""CLI utility to test graph traversal and multi-hop path retrieval in GraphRAGX."""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.graph.neo4j_client import get_graph_client
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.multi_hop_retriever import MultiHopRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAGX Multi-Hop Graph Traversal CLI")
    parser.add_argument(
        "--entity",
        "-e",
        type=str,
        required=True,
        help="Seed entity name or ID to start traversal from (e.g. 'Acme Corp', 'Product Nova')",
    )
    parser.add_argument(
        "--max-hops",
        "-m",
        type=int,
        default=2,
        help="Maximum number of relationship hops (default: 2)",
    )
    parser.add_argument(
        "--max-paths",
        "-p",
        type=int,
        default=10,
        help="Maximum paths to discover (default: 10)",
    )
    args = parser.parse_args()

    client = get_graph_client()
    stats = client.get_stats()

    # Auto-ingest if graph is empty
    if stats.get("entity_count", 0) == 0:
        print("Notice: Graph is empty. Performing automatic corpus ingestion...")
        pipeline = IngestionPipeline(data_dir="data/documents", client=client)
        pipeline.run()
        stats = client.get_stats()
        print(f"Graph ready: {stats.get('entity_count')} entities, {stats.get('relationship_count')} relationships.\n")

    retriever = MultiHopRetriever(client=client)
    result = retriever.retrieve(
        entity_name_or_id=args.entity,
        max_hops=args.max_hops,
        max_paths=args.max_paths,
    )

    print("==================================================")
    print(" GraphRAGX — Multi-Hop Graph Traversal")
    print("==================================================")
    print(f"Seed Entity: {result.seed_entity}")
    print(f"Max Hops   : {args.max_hops}")
    print(f"Paths Found: {len(result.paths)}")
    print(f"Facts Found: {len(result.facts)}")
    print(f"Evidence   : {len(result.evidence_chunks)} grounded chunks")
    print("==================================================\n")

    if not result.paths:
        print(f"No paths found starting from '{args.entity}'.")
        print("Tip: Check available entities or try another query name.")
        return

    print("--- Discovered Multi-Hop Paths ---")
    for i, path in enumerate(result.paths, start=1):
        cypher_repr = path.to_cypher_like()
        print(f"[{i}] {cypher_repr}")
        print(f"    Length: {path.length} hop(s) | Score: {path.score:.2f}")
        if path.evidence_chunk_ids:
            print(f"    Evidence Chunk IDs: {', '.join(path.evidence_chunk_ids)}")
        print()

    print("--- Relational Facts ---")
    for fact in result.facts:
        print(f"  • ({fact.source_name}) -[:{fact.relation}]-> ({fact.target_name})")
    print()

    if result.evidence_chunks:
        print("--- Grounded Evidence Chunks ---")
        for chunk in result.evidence_chunks:
            snippet = chunk.text.replace("\n", " ")[:140]
            print(f"  [{chunk.chunk_id}] (doc: {chunk.document_id})")
            print(f'    "{snippet}..."')
        print()


if __name__ == "__main__":
    main()
