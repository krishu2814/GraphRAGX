#!/usr/bin/env python3
"""CLI utility to execute the end-to-end knowledge ingestion pipeline into GraphRAGX."""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.ingestion.pipeline import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAGX Knowledge Graph Ingestion CLI")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/documents",
        help="Path to folder containing source markdown documents (default: data/documents)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable OpenAI LLM for extraction (default: false, uses deterministic rules)",
    )
    parser.add_argument(
        "--no-vectors",
        action="store_true",
        help="Skip dense vector indexing in Qdrant",
    )
    args = parser.parse_args()

    print("==================================================")
    print(" GraphRAGX — End-to-End Knowledge Ingestion")
    print("==================================================")
    print(f"Source Directory: {args.data_dir}")
    print(f"Extraction Mode : {'OpenAI LLM' if args.use_llm else 'Deterministic Rule-Based'}")
    print(f"Vector Indexing : {'Disabled' if args.no_vectors else 'Enabled'}\n")

    pipeline = IngestionPipeline(
        data_dir=args.data_dir,
        use_llm=args.use_llm,
        index_vectors=not args.no_vectors,
    )
    summary = pipeline.run()

    print("\n--------------------------------------------------")
    print(" Ingestion Summary")
    print("--------------------------------------------------")
    print(f"  Documents Processed       : {summary.documents_loaded}")
    print(f"  Semantic Chunks Created   : {summary.chunks_created}")
    print(f"  Vector Points Indexed     : {summary.vector_points_indexed}")
    print(f"  Raw Entities Extracted    : {summary.entities_extracted}")
    print(f"  Canonical Entities Formed : {summary.canonical_entities_count}")
    print(f"  Raw Relations Extracted   : {summary.raw_relationships_extracted}")
    print(f"  Resolved Graph Edges      : {summary.resolved_relationships_count}")
    print(f"  Pipeline Execution Time   : {summary.duration_ms} ms")
    print("\nGraph Database Store Counts:")
    for k, v in summary.graph_stats.items():
        label = k.replace("_", " ").title()
        print(f"  • {label:<24}: {v}")
    print("--------------------------------------------------")
    print("✔ Ingestion completed successfully.")


if __name__ == "__main__":
    main()
