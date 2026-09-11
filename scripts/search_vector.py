#!/usr/bin/env python3
"""CLI utility to test dense vector similarity retrieval on GraphRAGX collections."""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.retrieval.vector_retriever import VectorRetriever
from app.vector.vector_store import get_vector_store
from app.ingestion.pipeline import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAGX Vector Semantic Search CLI")
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="Natural language query to search for",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="Number of nearest chunks to retrieve (default: 5)",
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Optional document_id filter (e.g. service_identity)",
    )
    parser.add_argument(
        "--access-tier",
        type=str,
        default=None,
        help="Optional access tier filter (Public, Internal, Confidential, Restricted)",
    )
    args = parser.parse_args()

    store = get_vector_store()
    count = store.count()

    # If in-memory store is currently empty, automatically populate from data/documents
    if count == 0:
        print("Notice: Vector store is empty. Performing automatic corpus ingestion...")
        pipeline = IngestionPipeline(data_dir="data/documents", index_vectors=True)
        pipeline.run()
        count = store.count()
        print(f"Ingested {count} chunk vectors.\n")

    retriever = VectorRetriever(vector_store=store)

    print("==================================================")
    print(" GraphRAGX — Dense Vector Semantic Retrieval")
    print("==================================================")
    print(f"Query      : '{args.query}'")
    print(f"Top K      : {args.top_k}")
    if args.doc_id:
        print(f"Doc Filter : {args.doc_id}")
    if args.access_tier:
        print(f"Tier Filter: {args.access_tier}")
    print(f"Index Size : {count} points\n")

    results = retriever.retrieve(
        query=args.query,
        top_k=args.top_k,
        document_id=args.doc_id,
        access_tier=args.access_tier,
    )

    if not results:
        print("No matching chunks found.")
        return

    print("--------------------------------------------------------------------------------")
    print(f"{'Rank':<5} | {'Score':<7} | {'Chunk ID':<20} | {'Document':<20} | {'Section'}")
    print("--------------------------------------------------------------------------------")
    for chunk in results:
        meta = chunk.metadata or {}
        section = meta.get("section_title") or meta.get("title") or "General"
        doc = chunk.document_id or meta.get("document_id", "")
        print(f"{chunk.rank:<5} | {chunk.score:<7.4f} | {chunk.chunk_id:<20} | {doc:<20} | {section}")
        text_preview = chunk.text.replace("\n", " ").strip()
        if len(text_preview) > 120:
            text_preview = text_preview[:117] + "..."
        print(f"      Text: {text_preview}\n")
    print("--------------------------------------------------------------------------------")
    print(f"✔ Retrieved {len(results)} relevant chunks.")


if __name__ == "__main__":
    main()
