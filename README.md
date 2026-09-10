# GraphRAGX

Enterprise-grade Hybrid Knowledge Graph and Vector RAG system designed for complex relational, multi-hop, and global aggregation queries.

---

## Project Status: Lesson 1 Completed

The project is built incrementally across 16 focused lessons for clean git history and progress tracking. Comprehensive documentation for each lesson is stored in the [`docs/`](docs/) directory.

### Progress Tracker
- [x] [**Lesson 1: Project Setup, Configuration & Foundational Domain Models**](docs/lessons/01_project_setup_and_domain_models.md)
- [ ] **Lesson 2: Enterprise Knowledge Base & Document Corpus**
- [ ] **Lesson 3: Document Loading, Semantic Chunking & Metadata Extraction**
- [ ] **Lesson 4: Knowledge Extraction — Structured Entities & Relationships**
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

## Current Architecture: Foundational Domain Models (Lesson 1)

```
GraphRAGX/
├── app/
│   ├── config.py              # Pydantic Settings (Neo4j, Qdrant, OpenAI, RRF weights)
│   └── models/                # Strongly-typed domain models
│       ├── entities.py        # Entity, EntityType, CanonicalEntity
│       ├── relationships.py   # Relationship, RelationType, Evidence
│       ├── retrieval.py       # RetrievedChunk, GraphFact, RetrievalPath, FusionResult
│       ├── query.py           # QueryIntent, RetrievalPlan, LinkedEntity
│       └── responses.py       # QueryResponse, Citation, ComparisonResult
├── docs/                      # Dedicated project documentation
│   └── lessons/
│       └── 01_project_setup_and_domain_models.md
├── tests/
│   └── test_config_and_models.py # Unit test suite (11 tests)
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
└── README.md                  # Project overview and roadmap
```

---

## Getting Started

### 1. Environment Setup
Create and activate your virtual environment, then install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
*(By default, `USE_IN_MEMORY_GRAPH=true` and `USE_IN_MEMORY_VECTOR=true` allow running fully offline without external services).*

### 3. Run Verification Tests
```bash
pytest tests/ -v
```

For full technical details of the domain models and configuration system, see [Lesson 01 Documentation](docs/lessons/01_project_setup_and_domain_models.md).
