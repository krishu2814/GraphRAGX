"""Graph traversal engine for multi-hop path and relational fact discovery."""

from collections import deque
import logging
from typing import Any

from app.graph.neo4j_client import GraphClient, get_graph_client
from app.models.retrieval import GraphFact, RetrievalPath

logger = logging.getLogger(__name__)


class GraphTraverser:
    """Traverses knowledge graph relationships using Breadth-First Search (BFS)."""

    def __init__(self, client: GraphClient | None = None) -> None:
        self.client = client or get_graph_client()

    def find_paths(
        self,
        start_entity: str,
        max_hops: int = 2,
        max_paths: int = 20,
    ) -> list[RetrievalPath]:
        """Find multi-hop paths starting from an entity up to max_hops deep."""
        ent = self.client.get_entity(start_entity)
        if not ent:
            logger.info(f"Entity '{start_entity}' not found in graph.")
            return []

        start_id = ent["id"]
        start_name = ent.get("name", start_id)

        # BFS Queue item: (current_id, current_name, entities_list, relations_list, evidence_chunk_ids)
        queue = deque([(start_id, start_name, [start_name], [], [])])
        discovered_paths: list[RetrievalPath] = []

        while queue and len(discovered_paths) < max_paths:
            curr_id, curr_name, entities_path, relations_path, evidence_chunks = queue.popleft()

            # If we've made at least 1 hop, save this as a valid path
            if relations_path:
                hop_count = len(relations_path)
                score = round(1.0 / (1.0 + 0.25 * (hop_count - 1)), 3)
                discovered_paths.append(
                    RetrievalPath(
                        entities=entities_path,
                        relationships=relations_path,
                        length=hop_count,
                        score=score,
                        evidence_chunk_ids=evidence_chunks,
                        explanation=" -> ".join(entities_path),
                    )
                )

            # Stop expanding deeper if we reached max_hops
            if len(relations_path) >= max_hops:
                continue

            # Get 1-hop neighbors
            neighbors = self.client.get_neighbors(curr_id)
            for neighbor in neighbors:
                # We follow outgoing relationships
                if neighbor.get("direction") == "INCOMING":
                    continue

                target_id = neighbor["target_id"]
                target_name = neighbor.get("target_name", target_id)
                relation = neighbor.get("relation", "RELATED_TO")

                # Cycle prevention: don't revisit entities already in this path
                if target_name in entities_path or target_id in entities_path:
                    continue

                # Collect evidence chunk IDs
                new_evidence = list(evidence_chunks)
                for ev in neighbor.get("evidence", []):
                    chunk_id = ev.get("chunk_id") if isinstance(ev, dict) else getattr(ev, "chunk_id", None)
                    if chunk_id and chunk_id not in new_evidence:
                        new_evidence.append(chunk_id)

                new_entities = entities_path + [target_name]
                new_relations = relations_path + [relation]

                queue.append((target_id, target_name, new_entities, new_relations, new_evidence))

        return discovered_paths

    def find_facts(
        self,
        start_entity: str,
        max_hops: int = 2,
        max_facts: int = 30,
    ) -> list[GraphFact]:
        """Collect all relational facts discovered within max_hops of start_entity."""
        paths = self.find_paths(start_entity, max_hops=max_hops, max_paths=max_facts * 2)
        facts: list[GraphFact] = []
        seen_triples: set[tuple[str, str, str]] = set()

        for path in paths:
            for i in range(len(path.relationships)):
                src = path.entities[i]
                rel = path.relationships[i]
                tgt = path.entities[i + 1]

                triple_key = (src.lower(), rel.lower(), tgt.lower())
                if triple_key in seen_triples:
                    continue
                seen_triples.add(triple_key)

                ev_chunk = path.evidence_chunk_ids[0] if path.evidence_chunk_ids else ""
                facts.append(
                    GraphFact(
                        source_entity=src,
                        source_name=src,
                        relation=rel,
                        target_entity=tgt,
                        target_name=tgt,
                        evidence_chunk_id=ev_chunk,
                        confidence=path.score,
                    )
                )

                if len(facts) >= max_facts:
                    return facts

        return facts
