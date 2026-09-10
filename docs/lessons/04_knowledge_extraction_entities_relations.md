# Lesson 04: Knowledge Extraction — Structured Entities, Relationships & Entity Resolution

This document details the design, implementation, and verification of the structured knowledge extraction and entity resolution engines built in **Lesson 4** of GraphRAGX.

---

## 1. Overview & Objectives

Once documents are segmented into contextual chunks (Lesson 3), the next critical phase in GraphRAG is **transforming raw unstructured text into structured graph primitives**:
1. **Entity Extraction**: Identify named real-world concepts (Products, Microservices, Customers, Versions, Technologies, Policies) and classify them into standard `EntityType` categories.
2. **Relationship Extraction**: Extract directed relational triples (`Source` $\xrightarrow{\text{Type}}$ `Target`) and ground each fact with verifiable `Evidence` (source chunk ID and verbatim quotation).
3. **Entity Resolution & Canonicalization**: Bridge surface variations (e.g. *"Nova"*, *"Product Nova"*, *"Nova Platform"*) into a unified `CanonicalEntity` to prevent disconnected graph islands.

---

## 2. Architecture & Components

```
GraphRAGX/
├── app/
│   └── ingestion/
│       ├── __init__.py           # Exports extractors and resolver
│       ├── entity_extractor.py   # EntityExtractor (LLM + Deterministic rules)
│       ├── relation_extractor.py # RelationExtractor (Predicate matching + Evidence)
│       └── entity_resolution.py  # EntityResolver (Canonicalization & edge re-mapping)
├── docs/
│   └── lessons/
│       └── 04_knowledge_extraction_entities_relations.md
└── tests/
    └── test_extraction_and_resolution.py # Unit & integration tests (5 tests)
```

---

## 3. Implementation Details

### 3.1. Entity Extractor (`app/ingestion/entity_extractor.py`)
- **Dual Extraction Paradigm**:
  - **LLM Mode**: Uses OpenAI Chat Completion with Pydantic structured output parsing (`client.beta.chat.completions.parse`) targeting the `EntityExtractionResult` schema when an API key is configured.
  - **Deterministic Rule Mode**: A robust pattern-matching and lexicon-based engine utilizing compiled regex rules for zero-cost offline development, CI/CD, and offline testing.
- **Categorization & Normalization**:
  - Maps matches to `EntityType` enums (`PRODUCT`, `SERVICE`, `CUSTOMER`, `TECHNOLOGY`, `VERSION`, `POLICY`, `INCIDENT`).
  - Automatically derives deterministic node IDs: `entity:{type}:{slug}` (e.g. `entity:product:nova`).
  - Contextual descriptions are automatically extracted from surrounding sentence fragments.

### 3.2. Relationship Extractor (`app/ingestion/relation_extractor.py`)
- **Grounded Provenance**:
  - Every extracted edge carries an `Evidence` object linking directly to `chunk.chunk_id`, `chunk.document_id`, and the exact verbatim sentence from the chunk.
- **Predicate Inference**:
  - In deterministic mode, inspects linguistic cues and connectors between co-occurring entities:
    - *"relies on" / "delegates authentication to"* $\rightarrow$ `RelationType.DEPENDS_ON`
    - *"uses" / "deployed by" / "operates"* $\rightarrow$ `RelationType.USES`
    - *"affects" / "breaks" / "deprecated"* $\rightarrow$ `RelationType.AFFECTS`
    - *"introduced in" / "rolled out in"* $\rightarrow$ `RelationType.INTRODUCED_IN`
    - *"deploys to" / "hosted on"* $\rightarrow$ `RelationType.DEPLOYS_TO`
    - *"complies with" / "certified under"* $\rightarrow$ `RelationType.COMPLIES_WITH`

### 3.3. Entity Resolution & Canonicalization (`app/ingestion/entity_resolution.py`)
- **The Graph Fragmentation Problem**:
  If "Product Nova", "Nova", and "Nova Analytics" are stored as separate nodes, multi-hop traversals like:
  $$\text{Acme Corp} \rightarrow \text{Nova} \dots \text{Product Nova} \rightarrow \text{Identity Service}$$
  fail because the graph is physically disconnected.
- **Resolution Pipeline**:
  1. **Canonical Cluster Lookup**: Compares raw mentions against an indexed alias taxonomy using exact matching and substring containment.
  2. **Cluster Merging**: Consolidates multiple `Entity` mentions into a single `CanonicalEntity`, merging alias lists, source mention strings, and descriptions.
  3. **Edge Re-Mapping & Evidence Deduplication**: Re-links relationship endpoints from transient mention IDs to resolved canonical IDs. If multiple chunks state the same relationship, their `Evidence` entries are merged and edge `weight` is boosted, preserving multi-document consensus.

---

## 4. Verification & Testing

The test suite in [`tests/test_extraction_and_resolution.py`](../../tests/test_extraction_and_resolution.py) covers:
- `TestEntityExtractor`: Verifies correct extraction and categorization of Customer, Product, Service, Version, and Technology entities from unstructured text chunks.
- `TestRelationExtractor`: Validates that extracted relationships contain valid chunk provenance and quotation grounding.
- `TestEntityResolver`: Validates alias clustering (merging "Nova" and "Product Nova"), ID re-mapping, and edge deduplication.
- `TestEndToEndKnowledgeExtraction`: End-to-end integration test reading core corpus documents (`customer_acme.md`, `product_nova.md`, `authentication.md`, `incident_response.md`) through loaders, chunkers, extractors, and the resolver, verifying that cross-document multi-hop links (e.g. `(Nova)-[:DEPENDS_ON]->(Identity Service)`) are successfully formed.

Run the test suite:
```bash
./.venv/bin/pytest tests/test_extraction_and_resolution.py -v
```
All 5 tests pass in `0.11s`. Total project test count: **27 passing tests**.
