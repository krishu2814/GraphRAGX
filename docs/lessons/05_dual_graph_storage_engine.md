# Lesson 05: Dual Graph Storage Engine (Neo4j + In-Memory NetworkX Fallback)

This document details the design, architecture, and verification of the dual graph database storage layer built in **Lesson 5** of GraphRAGX.

---

## 1. Overview & Objectives

Knowledge Graphs require a dedicated property graph storage engine capable of:
1. **Idempotent Upserts**: Safely inserting nodes and relationships repeatedly without creating duplicate entities or duplicate edges.
2. **Schema & Integrity Constraints**: Enforcing unique identity constraints on entity identifiers, documents, and chunk IDs.
3. **Multi-Evidence Grounding**: Aggregating multiple evidence references onto single relationship edges when distinct documents corroborate the same fact.
4. **Dual Engine Flexibility**:
   - **Production Mode**: Full Neo4j connectivity via Bolt protocol with connection pooling, transactional retries, and parameterized Cypher.
   - **Offline / Test Mode**: High-performance in-memory `NetworkXGraphDriver` conforming to the exact same protocol, enabling unit testing, CI/CD pipelines, and local development with zero external dependencies.

---

## 2. Architecture & Components

```
GraphRAGX/
├── app/
│   └── graph/
│       ├── __init__.py           # Unified exports
│       ├── schema.py             # Labels, uniqueness constraints & index definitions
│       ├── cypher_queries.py     # Parameterized Cypher catalog
│       └── neo4j_client.py       # GraphClient ABC, NetworkXGraphDriver, Neo4jGraphDriver, Factory
├── docs/
│   └── lessons/
│       └── 05_dual_graph_storage_engine.md
└── tests/
    └── test_graph_engine.py      # Unit tests (9 tests)
```

---

## 3. Implementation Details

### 3.1. Graph Schema & Constraints (`app/graph/schema.py`)
Defines node labels and uniqueness constraints:
- **Node Labels**: `Entity`, `Document`, `Chunk`.
- **Uniqueness Constraints**:
  ```cypher
  CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
  CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
  CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
  ```
- **Performance Indexes**:
  ```cypher
  CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name);
  CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type);
  CREATE INDEX chunk_doc_id_idx IF NOT EXISTS FOR (c:Chunk) ON (c.document_id);
  ```

### 3.2. Parameterized Cypher Catalog (`app/graph/cypher_queries.py`)
All database interactions use parameterized queries to eliminate Cypher injection risks:
- `MERGE_ENTITY_NODE`: Idempotently merges `(e:Entity {id: $id})` and updates name, type, description, and aliases.
- `MERGE_DOCUMENT_NODE` & `MERGE_CHUNK_NODE`: Idempotently store documents and chunks with structural metadata.
- `LINK_CHUNK_TO_DOCUMENT`: Creates `(Chunk)-[:PART_OF]->(Document)`.
- `LINK_CHUNK_TO_ENTITY`: Creates `(Chunk)-[:MENTIONS]->(Entity)`.
- `build_merge_relationship_query()`: Dynamically builds sanitized parameterized Cypher for dynamic relation types:
  ```cypher
  MATCH (s:Entity {id: $source_id})
  MATCH (t:Entity {id: $target_id})
  MERGE (s)-[r:REL_TYPE]->(t)
  SET r.description = $description, r.weight = $weight, r.evidence = $evidence
  ```
- `GET_NEIGHBORS_1HOP` & `GET_GRAPH_STATS`: 1-hop inspection and graph health metrics.

### 3.3. Unified `GraphClient` & Dual Drivers (`app/graph/neo4j_client.py`)
- **`GraphClient` Abstract Interface**: Defines the contract (`add_entity`, `add_document`, `add_chunk`, `add_relationship`, `link_chunk_to_entity`, `get_entity`, `get_neighbors`, `get_stats`, `clear`, `close`).
- **`NetworkXGraphDriver`**:
  - Implements the interface using `networkx.MultiDiGraph`.
  - Maintains an internal alias-to-ID lookup index supporting instantaneous case-insensitive alias lookups.
  - Automatically merges evidence arrays and increments edge weight upon duplicate relationship insertion.
- **`Neo4jGraphDriver`**:
  - Implements the interface over official `neo4j.GraphDatabase.driver` using managed sessions and transactions.
- **`get_graph_client()` Factory**:
  - Respects `USE_IN_MEMORY_GRAPH=true` by default.
  - When configured for live Neo4j, attempts connection and gracefully falls back to `NetworkXGraphDriver` if the database is unreachable, logging a warning rather than crashing.

---

## 4. Verification & Testing

The test suite in [`tests/test_graph_engine.py`](../../tests/test_graph_engine.py) covers:
1. `TestGraphSchema`: Validates Cypher constraint definitions and dynamic relationship query generation.
2. `TestNetworkXGraphDriver`:
   - Entity insertion and retrieval by canonical ID, standard name, and alias.
   - Document and chunk insertion with `PART_OF` edge verification.
   - Relationship insertion with multi-chunk evidence deduplication.
   - 1-hop neighbor traversal across incoming and outgoing directions.
   - Graph statistics calculation and graph clearing.
3. `TestGraphClientFactory`: Confirms default offline fallback and forced in-memory initialization.

Run the test suite:
```bash
./.venv/bin/pytest tests/test_graph_engine.py -v
```
All 9 tests pass in `0.26s`. Total project test count: **36 passing tests**.
