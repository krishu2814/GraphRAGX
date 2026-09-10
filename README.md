# GraphRAGX

Enterprise-grade Hybrid Knowledge Graph and Vector RAG system designed for complex relational, multi-hop, and global aggregation queries.

---

## Project Status: Lesson 4 Completed

The project is built incrementally across 16 focused lessons for clean git history and progress tracking. Comprehensive documentation for each lesson is stored in the [`docs/`](docs/) directory.

### Progress Tracker
- [x] [**Lesson 1: Project Setup, Configuration & Foundational Domain Models**](docs/lessons/01_project_setup_and_domain_models.md)
- [x] [**Lesson 2: Enterprise Knowledge Base & Document Corpus**](docs/lessons/02_enterprise_knowledge_base.md)
- [x] [**Lesson 3: Document Loading, Semantic Chunking & Metadata Extraction**](docs/lessons/03_document_loading_chunking_metadata.md)
- [x] [**Lesson 4: Knowledge Extraction — Structured Entities & Relationships**](docs/lessons/04_knowledge_extraction_entities_relations.md)
- [ ] **Lesson 5: Dual Graph Storage Engine (Neo4j + In-Memory NetworkX)**
- [ ] **Lesson 6: Graph Builder & Idempotent Ingestion Pipeline**
- [ ] **Lesson 7: Vector Storage & Dense Semantic Retrieval**
- [ ] **Lesson 8: Graph Traversal & Multi-Hop Path Retrieval**
- [ ] **Lesson 9: Query Understanding, Intent Classification & Entity Linking**
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
│   └── ingestion/             # Ingestion, Extraction & Canonicalization
│       ├── loaders.py         # MarkdownLoader & section hierarchy parsing
│       ├── metadata.py        # MetadataEnricher & entity hint detection
│       ├── chunker.py         # Structure-aware SemanticChunker
│       ├── entity_extractor.py   # Dual LLM & rule-based EntityExtractor
│       ├── relation_extractor.py # Grounded RelationExtractor with evidence quotes
│       └── entity_resolution.py  # Canonicalization & alias deduplication
├── data/
│   └── documents/             # 20 interconnected enterprise markdown documents
├── docs/                      # Technical documentation
│   └── lessons/
│       ├── 01_project_setup_and_domain_models.md
│       ├── 02_enterprise_knowledge_base.md
│       ├── 03_document_loading_chunking_metadata.md
│       └── 04_knowledge_extraction_entities_relations.md
├── tests/
│   ├── test_config_and_models.py # Unit tests (11 tests)
│   ├── test_documents.py         # Corpus validation tests (3 tests)
│   ├── test_chunking.py          # Loader & chunker tests (8 tests)
│   └── test_extraction_and_resolution.py # Extractor & resolver tests (5 tests)
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

### 2. Run Verification Tests
```bash
pytest tests/ -v
```

See [docs/lessons/](docs/lessons/) for technical deep-dives into each milestone.
