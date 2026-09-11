"""Multi-hop graph retriever discovering connected paths, facts, and evidence chunks."""

import logging
from typing import Any

from app.graph.neo4j_client import GraphClient, get_graph_client
from app.graph.traversal import GraphTraverser
from app.models.retrieval import MultiHopResult, RetrievedChunk
from app.vector.vector_store import VectorStore

logger = logging.getLogger(__name__)


class MultiHopRetriever:
    """Retrieves multi-hop paths, facts, and evidence chunks from the knowledge graph."""

    def __init__(
        self,
        client: GraphClient | None = None,
        traverser: GraphTraverser | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.client = client or get_graph_client()
        self.traverser = traverser or GraphTraverser(self.client)
        self.vector_store = vector_store

    def retrieve(
        self,
        entity_name_or_id: str,
        max_hops: int = 2,
        max_paths: int = 20,
    ) -> MultiHopResult:
        """Find relational paths and facts starting from an entity, plus grounded evidence chunks."""
        query_entity = entity_name_or_id.strip()
        if not query_entity:
            return MultiHopResult(seed_entity=entity_name_or_id)

        # 1. Discover multi-hop paths using BFS
        paths = self.traverser.find_paths(
            start_entity=query_entity,
            max_hops=max_hops,
            max_paths=max_paths,
        )

        # 2. Extract unique relational facts along these paths
        facts = self.traverser.find_facts(
            start_entity=query_entity,
            max_hops=max_hops,
        )

        # 3. Gather evidence chunk IDs from paths
        evidence_chunk_ids: list[str] = []
        for path in paths:
            for cid in path.evidence_chunk_ids:
                if cid and cid not in evidence_chunk_ids:
                    evidence_chunk_ids.append(cid)

        # 4. Fetch the full chunk text/metadata
        evidence_chunks: list[RetrievedChunk] = []
        for rank, chunk_id in enumerate(evidence_chunk_ids, start=1):
            chunk_data = self.client.get_chunk(chunk_id)
            if chunk_data:
                evidence_chunks.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        document_id=chunk_data.get("document_id", ""),
                        text=chunk_data.get("text", ""),
                        score=1.0,
                        rank=rank,
                        metadata=chunk_data,
                    )
                )

        return MultiHopResult(
            seed_entity=query_entity,
            paths=paths,
            facts=facts,
            evidence_chunks=evidence_chunks,
        )
