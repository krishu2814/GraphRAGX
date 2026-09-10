#!/usr/bin/env python3
"""CLI utility to initialize graph schema constraints and indexes."""

import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.graph.neo4j_client import get_graph_client
from app.graph.schema import CONSTRAINTS, INDEXES


def main() -> None:
    print("==================================================")
    print(" GraphRAGX — Graph Database Schema Initialization")
    print("==================================================")

    client = get_graph_client()
    print(f"Target Driver: {client.__class__.__name__}")

    print("\n[1/2] Creating Uniqueness Constraints:")
    for c in CONSTRAINTS:
        print(f"  + {c}")

    print("\n[2/2] Creating Performance Indexes:")
    for idx in INDEXES:
        print(f"  + {idx}")

    client.initialize_schema()
    print("\n✔ Schema initialized successfully.")
    client.close()


if __name__ == "__main__":
    main()
