# Lesson 07: Vector Storage & Dense Semantic Retrieval

This document details the design, mathematical formulation, architecture, and verification of the dense vector embedding, storage, and semantic retrieval subsystem implemented in **Lesson 7** of GraphRAGX.

---

## 1. Overview & Objectives

In GraphRAGX, the hybrid knowledge engine relies on two complementary retrieval pillars:
1. **Symbolic Knowledge Graph**: Explores explicit relational paths, multi-hop dependencies, and ontological communities.
2. **Dense Semantic Vector Store**: Captures unstructured textual meaning, nuance, technical synonyms, and fuzzy descriptions across document chunks.

The primary objectives for Lesson 7:
- **Zero-Dependency Offline Embeddings**: Implement an `EmbeddingService` that interfaces seamlessly with OpenAI text embeddings when API credentials exist, but falls back to a deterministic, zero-latency n-gram feature-hashing projection ($L_2$ unit-normalized) when offline or in test environments.
- **Qdrant Vector Database Integration**: Build `QdrantVectorStore` supporting in-memory mode (`:memory:`) for test isolation alongside production HTTP connections.
- **Idempotent Chunk Indexing**: Convert `DocumentChunk` models into vector points identified by deterministic DNS UUID5 hashes, storing rich structured payloads (document ID, section path, access security tier, entity hints).
- **Dense Vector Retrieval**: Implement `VectorRetriever` to rank nearest neighbor chunks by cosine similarity, with support for document and access-tier metadata filtering.
- **Unified Pipeline & CLI**: Extend `IngestionPipeline` and `scripts/ingest.py` to index vector embeddings automatically, and provide `scripts/search_vector.py` for interactive retrieval inspection.

---

## 2. Architecture & Data Flow

```mermaid
graph TD
    A["Semantic Chunks<br/>(from SemanticChunker)"] -->|embed_batch| B["EmbeddingService<br/>(OpenAI / Deterministic Fallback)"]
    B -->|Dense Float Vectors<br/>dim=1536, L2=1.0| C["QdrantVectorStore<br/>(Collection: graphragx_chunks)"]
    A -->|Payload (chunk_id, doc_id, access_tier)| C

    subgraph "Query & Retrieval Phase"
        Q["User Query String"] -->|embed_text| B
        B -->|Query Vector| R["VectorRetriever"]
        C -->|Cosine Search & Filters| R
        R -->|Ranked & Scored| RC["RetrievedChunk Models<br/>(score, rank, chunk_id, text, metadata)"]
    end
```

---

## 3. Implementation Details

### 3.1. Embedding Service (`app/vector/embeddings.py`)

The `DefaultEmbeddingService` provides a unified embedding interface:
- **Production Mode**: When `openai_api_key` is configured, calls `OpenAI().embeddings.create()` with model `text-embedding-3-small`.
- **Deterministic Offline Fallback**: Generates pseudo-semantic dense vectors using a feature hashing trick:
  $$\vec{v}[h_{\text{index}}(\text{token})] += \text{sign}(h_{\text{sign}}(\text{token})) \times w_{\text{token}}$$
  - Computes SHA-256 digests of lowercase word tokens and character 3-grams.
  - Projects tokens across `dimension` dimensions (default: 1536) with signed hash weights.
  - Applies $L_2$ unit normalization:
    $$\hat{\vec{v}} = \frac{\vec{v}}{\|\vec{v}\|_2}$$
  - Guarantees that cosine similarity between vectors $\hat{\vec{u}} \cdot \hat{\vec{v}}$ directly reflects token and subword overlap while remaining completely deterministic and requiring zero third-party model downloads.

### 3.2. Qdrant Vector Store (`app/vector/vector_store.py`)

The `QdrantVectorStore` manages collection lifecycle and point indexing:
- **Storage Modes**:
  - `use_in_memory_vector=True`: Runs Qdrant `:memory:` client directly in-process with zero network overhead.
  - Production: Connects via HTTP to `settings.qdrant_url` (e.g. `http://localhost:6333`). If connection fails, logs a warning and engages in-memory fallback.
- **Collection Management**: Automatically creates collection `graphragx_chunks` configured with `Distance.COSINE` and vector size `1536`.
- **Point Structure**:
  - **ID**: `uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id)` ensuring strict idempotency upon re-indexing.
  - **Payload**: Preserves `chunk_id`, `document_id`, `text`, `section_title`, `section_path`, `access_tier`, and `metadata`.
- **Filtered Similarity Search**: Utilizes `client.query_points` with optional `Filter(must=[FieldCondition(...)])` targeting specific documents or security tiers.

### 3.3. Dense Semantic Retriever (`app/retrieval/vector_retriever.py`)

The `VectorRetriever` orchestrates query embedding and nearest-neighbor search:
- Validates query strings and generates the query vector.
- Constructs field filter dictionaries (supporting `document_id`, `access_tier`, and arbitrary extra attributes).
- Converts raw Qdrant points into domain models (`RetrievedChunk`) with 1-based ranks and calibrated cosine scores.

### 3.4. Ingestion Pipeline Integration (`app/ingestion/pipeline.py`)

Extended `IngestionPipeline` with a 6th execution stage:
- **Step 6/6**: Automatically embeds all generated `DocumentChunk` instances and performs batch upsert into `VectorStore`.
- Tracks `vector_points_indexed` in `IngestionSummary`.

---

## 4. Verification & Testing

### 4.1. Automated Test Suite (`tests/test_vector_retrieval.py`)

Thirteen unit and integration tests validate the vector retrieval subsystem:
1. `TestEmbeddingService`:
   - `test_embedding_dimensions_and_normalization`: Validates 1536 dimensions and unit $L_2$ norm.
   - `test_batch_embedding_consistency`: Asserts batch embeddings match individual embeddings.
   - `test_empty_or_whitespace_embedding`: Ensures resilient handling of empty/whitespace inputs.
   - `test_semantic_similarity_differentiation`: Confirms related queries yield higher cosine similarity than unrelated technical queries.
2. `TestQdrantVectorStore`:
   - `test_in_memory_initialization_and_upsert`: Verifies collection creation and point counts.
   - `test_idempotent_upsert`: Verifies re-indexing the same chunks does not create duplicates.
   - `test_payload_preservation`: Asserts all chunk metadata attributes are retained in search results.
   - `test_filtered_similarity_search`: Verifies filtering by document ID and access tier.
   - `test_clear_collection`: Tests resetting the vector collection.
3. `TestVectorRetriever`:
   - `test_retrieve_ranked_chunks`: Confirms 1-based ranks and descending score order.
   - `test_empty_query_returns_empty_list`: Verifies empty query handling.
   - `test_top_k_parameter`: Verifies top-k retrieval bounds.
4. `TestPipelineVectorIntegration`:
   - `test_full_corpus_vector_indexing`: Ingests all 20 corpus documents, verifying that all 96 chunks are indexed into the vector store and retrieved by semantic search.

Execute tests via:
```bash
.venv/bin/pytest tests/test_vector_retrieval.py -v
```

### 4.2. CLI Semantic Retrieval Demonstration

Search the corpus vector index via `scripts/search_vector.py`:

```bash
$ python scripts/search_vector.py --query "OAuth 2.1 breaking change and deprecations" --top-k 3

==================================================
 GraphRAGX — Dense Vector Semantic Retrieval
==================================================
Query      : 'OAuth 2.1 breaking change and deprecations'
Top K      : 3
Index Size : 96 points

--------------------------------------------------------------------------------
Rank  | Score   | Chunk ID             | Document             | Section
--------------------------------------------------------------------------------
1     | 0.2863  | chunk_version_history_001 | version_history      | CloudScale Systems Platform — Version History & Changelog
      Text: This changelog outlines major, minor, and breaking changes across CloudScale Systems platform releases, detailing arc...

2     | 0.2116  | chunk_product_nova_003 | product_nova         | Service Dependencies
      Text: 1. **Identity Service**: Product Nova delegates all user authentication and token exchange to Identity Service. In ve...

3     | 0.2101  | chunk_version_history_004 | version_history      | Breaking Changes & Deprecations
      Text: - **BREAKING**: OAuth 2.0 Implicit Grant flow is permanently removed from **Identity Service**. Clients connecting to...

--------------------------------------------------------------------------------
✔ Retrieved 3 relevant chunks.
```

---

## 5. Summary & Next Steps

With **Lesson 7** complete:
- Chunks across the 20-document enterprise corpus are indexed as dense vectors in Qdrant alongside symbolic graph nodes in Neo4j/NetworkX.
- Dense semantic search allows rapid discovery of relevant text sections based on natural language queries.
- In **Lesson 8**, we build **Graph Traversal & Multi-Hop Path Retrieval** (`app/graph/traversal.py` and `app/retrieval/multi_hop_retriever.py`) to traverse multi-step entity dependency chains ($A \rightarrow B \rightarrow C$).
