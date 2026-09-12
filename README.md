# GraphRAGX

Enterprise-grade Hybrid Knowledge Graph and Vector RAG system designed for complex relational, multi-hop, and global aggregation queries.

---

## Project Status: Lesson 9 Completed

The project is built incrementally across 16 focused lessons for clean git history and progress tracking. Comprehensive documentation for each lesson is stored in the [`docs/`](docs/) directory.

### Progress Tracker
- [x] [**Lesson 1: Project Setup, Configuration & Foundational Domain Models**](docs/lessons/01_project_setup_and_domain_models.md)
- [x] [**Lesson 2: Enterprise Knowledge Base & Document Corpus**](docs/lessons/02_enterprise_knowledge_base.md)
- [x] [**Lesson 3: Document Loading, Semantic Chunking & Metadata Extraction**](docs/lessons/03_document_loading_chunking_metadata.md)
- [x] [**Lesson 4: Knowledge Extraction — Structured Entities & Relationships**](docs/lessons/04_knowledge_extraction_entities_relations.md)
- [x] [**Lesson 5: Dual Graph Storage Engine (Neo4j + In-Memory NetworkX)**](docs/lessons/05_dual_graph_storage_engine.md)
- [x] [**Lesson 6: Graph Builder & Idempotent Ingestion Pipeline**](docs/lessons/06_graph_builder_ingestion_pipeline.md)
- [x] [**Lesson 7: Vector Storage & Dense Semantic Retrieval**](docs/lessons/07_vector_storage_semantic_retrieval.md)
- [x] [**Lesson 8: Graph Traversal & Multi-Hop Path Retrieval**](docs/lessons/08_graph_traversal_multihop_retrieval.md)
- [x] [**Lesson 9: Query Understanding, Intent Classification & Entity Linking**](docs/lessons/09_query_understanding_intent_entity_linking.md)
- [ ] **Lesson 10: Community Detection & Global GraphRAG**
- [ ] **Lesson 11: Hybrid Fusion (RRF) & Graph-Aware Reranker**
- [ ] **Lesson 12: Grounded Response Generation & Traceable Citations**
- [ ] **Lesson 13: Observability, Diagnostic Tracing & Unified CLI**
- [ ] **Lesson 14: Golden Benchmark Dataset & Systematic Evaluation**
- [ ] **Lesson 15: FastAPI REST API & Streamlit Debugger Dashboard**
- [ ] **Lesson 16: End-to-End Test Suite, Docker & Production Documentation**

---

## Current Architecture

```
GraphRAGX/
├── app/
│   ├── config.py              # Pydantic Settings (Neo4j, Qdrant, OpenAI, RRF weights)
│   ├── models/                # Strongly-typed domain models
│   │   ├── entities.py        # Entity, EntityType, CanonicalEntity
│   │   ├── relationships.py   # Relationship, RelationType, Evidence
│   │   ├── retrieval.py       # RetrievedChunk, GraphFact, RetrievalPath, FusionResult
│   │   ├── query.py           # QueryIntent, RetrievalPlan, LinkedEntity
│   │   └── responses.py       # QueryResponse, Citation, ComparisonResult
│   ├── ingestion/             # Ingestion, Extraction & Pipeline
│   │   ├── loaders.py         # MarkdownLoader & section hierarchy parsing
│   │   ├── metadata.py        # MetadataEnricher & entity hint detection
│   │   ├── chunker.py         # Structure-aware SemanticChunker
│   │   ├── entity_extractor.py   # Dual LLM & rule-based EntityExtractor
│   │   ├── relation_extractor.py # Grounded RelationExtractor with evidence quotes
│   │   ├── entity_resolution.py  # Canonicalization & alias deduplication
│   │   ├── graph_builder.py   # Idempotent GraphBuilder
│   │   └── pipeline.py        # IngestionPipeline coordinator
│   ├── graph/                 # Dual Graph Storage & Traversal Engine
│   │   ├── schema.py          # Labels, constraints, and indexes
│   │   ├── cypher_queries.py  # Parameterized Cypher catalog
│   │   ├── neo4j_client.py    # GraphClient protocol, NetworkX & Neo4j drivers
│   │   └── traversal.py       # BFS multi-hop path exploration & fact discovery
│   ├── vector/                # Dense Vector Storage Engine
│   │   ├── embeddings.py      # EmbeddingService (OpenAI & offline hashing fallback)
│   │   └── vector_store.py    # QdrantVectorStore (:memory: & remote Qdrant)
│   ├── retrieval/             # Information Retrieval Subsystem
│   │   ├── vector_retriever.py    # Semantic similarity search & metadata filtering
│   │   └── multi_hop_retriever.py # Multi-hop path retrieval & grounded chunk resolution
│   └── query/                 # Query Understanding & Planning Subsystem
│       ├── entity_linker.py   # Greedy longest-match entity linking
│       ├── intent_classifier.py # 7-intent classification with heuristics + LLM
│       ├── planner.py         # RetrievalStrategy & hop budget planner
│       └── analyzer.py        # Unified QueryAnalyzer orchestration facade
├── data/
│   └── documents/             # 20 interconnected enterprise markdown documents
├── docs/                      # Technical documentation
│   └── lessons/
│       ├── 01_project_setup_and_domain_models.md
│       ├── 02_enterprise_knowledge_base.md
│       ├── 03_document_loading_chunking_metadata.md
│       ├── 04_knowledge_extraction_entities_relations.md
│       ├── 05_dual_graph_storage_engine.md
│       ├── 06_graph_builder_ingestion_pipeline.md
│       ├── 07_vector_storage_semantic_retrieval.md
│       ├── 08_graph_traversal_multihop_retrieval.md
│       └── 09_query_understanding_intent_entity_linking.md
├── scripts/
│   ├── build_graph.py         # Schema initialization CLI
│   ├── ingest.py              # End-to-end ingestion runner CLI (graph + vectors)
│   ├── search_vector.py       # Dense semantic retrieval inspection CLI
│   ├── traverse_graph.py      # Multi-hop graph traversal & path inspection CLI
│   └── analyze_query.py       # Query understanding & retrieval planning CLI
├── tests/
│   ├── test_config_and_models.py # Unit tests (11 tests)
│   ├── test_documents.py         # Corpus validation tests (3 tests)
│   ├── test_chunking.py          # Loader & chunker tests (8 tests)
│   ├── test_extraction_and_resolution.py # Extractor & resolver tests (6 tests)
│   ├── test_graph_engine.py      # Dual graph driver tests (9 tests)
│   ├── test_graph_traversal.py   # Traversal & multi-hop tests (10 tests)
│   ├── test_ingestion_pipeline.py # Pipeline integration tests (2 tests)
│   ├── test_vector_retrieval.py  # Vector store & retriever tests (13 tests)
│   └── test_query_understanding.py # Entity linking, intent & planner tests (20 tests)
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
└── README.md                  # Project overview and roadmap
```

---

## Getting Started

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run End-to-End Ingestion CLI (Graph + Vectors)
```bash
python scripts/ingest.py --data-dir data/documents
```

### 3. Run Semantic Vector Search CLI
```bash
python scripts/search_vector.py --query "OAuth 2.1 breaking changes" --top-k 3
```

### 4. Run Multi-Hop Graph Traversal CLI
```bash
python scripts/traverse_graph.py --entity "Acme Corp" --max-hops 2
```

### 5. Run Query Understanding & Retrieval Planning CLI
```bash
python scripts/analyze_query.py --query "How does Acme Corp depend on Identity Service?"
```

### 6. Run Verification Tests (82 Tests)
```bash
pytest tests/ -v
```

See [docs/lessons/](docs/lessons/) for technical deep-dives into each milestone.

