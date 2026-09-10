# Lesson 01: Project Setup, Configuration & Foundational Domain Models

This document details the architectural design, implementation details, and verification steps for **Lesson 1** of GraphRAGX.

---

## 1. Overview & Objectives

In GraphRAG systems, data flows through multiple distinct representation layers:
1. **Raw Text Chunks**: Unstructured document fragments.
2. **Knowledge Graph Subgraphs**: Nodes (Entities) and directed Edges (Relationships) with evidence pointers.
3. **Retrieval Paths & Facts**: Multi-hop traversals and localized neighborhoods.
4. **Fused Ranked Candidates**: Hybrid combinations of dense semantic similarities and graph structural scores.
5. **Grounded Answers with Citations**: LLM-synthesized responses with verified attribution back to source chunks.

To prevent schema drift and runtime errors across these layers, Lesson 1 establishes:
- Strongly typed domain models using Pydantic v2.
- An environment configuration system with zero-setup offline fallback capability.
- Unit testing infrastructure.

---

## 2. Directory Structure

```
GraphRAGX/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings & environment loading
│   └── models/                   # Centralized type system
│       ├── __init__.py           # Unified exports
│       ├── entities.py           # Entity, EntityType, CanonicalEntity
│       ├── relationships.py      # Relationship, RelationType, Evidence
│       ├── retrieval.py          # RetrievedChunk, GraphFact, RetrievalPath, FusionResult
│       ├── query.py              # QueryIntent, RetrievalPlan, LinkedEntity
│       └── responses.py          # QueryResponse, Citation, ComparisonResult
├── docs/
│   └── lessons/
│       └── 01_project_setup_and_domain_models.md
├── tests/
│   ├── __init__.py
│   └── test_config_and_models.py # Unit tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusions
├── requirements.txt              # Pinned dependencies
└── README.md                     # Repository root overview
```

---

## 3. Implementation Details

### 3.1. Configuration Management (`app/config.py`)
Built on `pydantic-settings`, the `Settings` class manages all environment variables with default values that enable **immediate offline development**:
- **Dual Engine Flags**:
  - `use_in_memory_graph: bool = True`: Enables an in-memory NetworkX graph driver when Neo4j is offline.
  - `use_in_memory_vector: bool = True`: Enables an in-memory cosine vector store when Qdrant is offline.
- **RRF Weighting Parameters**: Configurable `vector_weight` (0.5), `graph_weight` (0.3), `entity_weight` (0.2), and smoothing factor `rrf_k` (60).
- **Singleton Pattern**: Cached via `@lru_cache(maxsize=1)` in `get_settings()` to avoid redundant file I/O.

### 3.2. Entity Models (`app/models/entities.py`)
- **`EntityType`**: Standardized enum taxonomy covering `PRODUCT`, `SERVICE`, `CUSTOMER`, `TECHNOLOGY`, `VERSION`, `PLAN`, `ORGANIZATION`, `POLICY`, `INCIDENT`, and `CONCEPT`.
- **`Entity`**: Represents an extracted or stored graph node. Features `add_alias()` which performs case-insensitive deduplication against the canonical name and existing aliases.
- **`CanonicalEntity`**: Represents an entity post-resolution, aggregating multiple mentions and surface aliases across documents.

### 3.3. Relationship & Provenance Models (`app/models/relationships.py`)
- **`RelationType`**: Directed edge categories (`DEPENDS_ON`, `USES`, `AFFECTS`, `INTRODUCED_IN`, `SUPPORTS`, `DEPLOYS_TO`, etc.).
- **`Evidence`**: Essential for enterprise GraphRAG auditability. Binds each relationship to its source `chunk_id`, `document_id`, and exact verbatim `text` quote with an extraction confidence score.
- **`Relationship`**: Directed graph edge linking `source_id` to `target_id`. Includes `add_evidence()` with automatic deduplication by `chunk_id`.

### 3.4. Retrieval & Fusion Models (`app/models/retrieval.py`)
- **`RetrievedChunk`**: Standard unit of vector retrieval containing text, similarity score, rank, and chunk metadata.
- **`GraphFact`**: Atomic relational fact retrieved from the graph (e.g., `(Nova)-[:DEPENDS_ON]->(Identity Service)`).
- **`RetrievalPath`**: Multi-hop traversal sequence. Provides `to_cypher_like()` to format paths into readable Cypher-like strings (e.g. `(Acme)-[:USES]->(Nova)-[:DEPENDS_ON]->(Identity Service)`).
- **`FusionResult`**: Fused candidate model tracking individual vector score, vector rank, graph score, graph rank, RRF score, and contributing multi-hop paths.

### 3.5. Query & Response Models (`app/models/query.py`, `app/models/responses.py`)
- **`QueryIntent`**: Classifies incoming queries into `DIRECT_FACT`, `ENTITY_LOOKUP`, `RELATIONSHIP`, `MULTI_HOP`, `GLOBAL`, `COMPARISON`, or `NO_ANSWER`.
- **`RetrievalPlan`**: Output of query analysis, specifying selected strategy, seed entities, max graph hops, and filters.
- **`Citation`**: Source-traceable quotation mapping answers to specific chunk IDs.
- **`ComparisonResult`**: Side-by-side evaluation artifact containing responses from Vector, Graph, and Hybrid strategies alongside differential analysis.

---

## 4. Verification & Testing

The test suite in `tests/test_config_and_models.py` validates:
1. Default configuration values and singleton caching.
2. Entity creation, alias addition, and case-insensitive deduplication.
3. Relationship validation, confidence range bounds (`0.0 <= confidence <= 1.0`), and evidence deduplication.
4. Cypher-like ASCII path formatting for multi-hop graph paths.
5. Query planning, response serialization, and strategy comparison data structures.

Execute tests via:
```bash
./.venv/bin/pytest tests/ -v
```
All 11 tests pass with 100% coverage over the domain model definitions.
