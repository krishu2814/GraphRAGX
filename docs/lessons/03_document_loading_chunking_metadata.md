# Lesson 03: Document Loading, Semantic Chunking & Metadata Extraction

This document details the design, architecture, and verification of the document loading, structure-aware semantic chunking, and metadata enrichment engine built in **Lesson 3** of GraphRAGX.

---

## 1. Overview & Objectives

In knowledge graph construction and hybrid RAG, chunking is not just a text splitting mechanism; it is the **grounding substrate** for all entities, relationships, and vector embeddings:
1. **Provenance Grounding**: In enterprise systems, every relationship edge in the graph must cite the exact `chunk_id` where that relationship was stated.
2. **Context Loss Prevention**: Naive chunking (splitting strictly every $N$ tokens) bisects entity relationships and strips header hierarchy. A chunk stating:
   > *"It relies on Identity Service for authentication."*
   is useless in isolation unless the chunk carries the section path:
   > `CloudScale Systems > Product Portfolio Catalog > Product Nova`
3. **Deterministic Chunk IDs**: Chunk IDs must remain stable and reproducible across repeated ingestion runs (e.g. `chunk_product_nova_001`).

Lesson 3 builds a structure-aware ingestion pipeline that preserves markdown section hierarchies, enforces token boundaries, and extracts domain entity hints to accelerate downstream graph extraction.

---

## 2. Architectural Components

```
GraphRAGX/
├── app/
│   └── ingestion/
│       ├── __init__.py           # Unified exports
│       ├── loaders.py            # MarkdownLoader & LoadedDocument
│       ├── metadata.py           # MetadataEnricher, ChunkMetadata, AccessTier
│       └── chunker.py            # SemanticChunker & DocumentChunk
├── docs/
│   └── lessons/
│       └── 03_document_loading_chunking_metadata.md
└── tests/
    └── test_chunking.py          # Unit tests (8 tests)
```

---

## 3. Implementation Details

### 3.1. MarkdownLoader (`app/ingestion/loaders.py`)
- **YAML Frontmatter Extraction**: Parses document metadata headers (`title`, `document_id`, `department`, `access_tier`, `version`, `last_updated`) using regex matching and type coercion.
- **Fallback Resolution**: If frontmatter is absent, automatically derives `document_id` from filename and `title` from the first markdown H1 header.
- **Heading Stack Parsing**: Employs a stateful heading stack to track nested markdown hierarchies (`#`, `##`, `###`), outputting structured `MarkdownSection` objects with exact breadcrumb paths (e.g., `Product Nova Architecture > Core Capabilities > Service Dependencies`).

### 3.2. MetadataEnricher (`app/ingestion/metadata.py`)
- **Access Tier Validation**: Normalizes string representations into the `AccessTier` enum (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).
- **Heuristic Token Estimation**: Calculates character count, word count, and token count approximations (~4 characters per token).
- **Candidate Entity Hint Scanner**: Scans chunk text against compiled regex patterns for enterprise products (`Nova`, `Orion`, `Atlas`, `Vega`), microservices (`Identity Service`, `Policy Engine`, `Gateway Service`), enterprise customers (`Acme Corp`, `Globex Corp`, `Initech`), protocols (`OAuth 2.1`, `PKCE`, `PASETO`), and infrastructure (`AWS`, `Azure`, `EKS`, `AKS`). These hints act as high-precision anchors for entity extraction in **Lesson 4**.

### 3.3. SemanticChunker (`app/ingestion/chunker.py`)
- **Section-First Chunking**: Documents are split first along semantic section boundaries. Content belonging to separate topics is never merged into a single chunk.
- **Paragraph & Sentence Boundaries**: Sections are subdivided along natural double-newline paragraph breaks. If a paragraph exceeds the target `chunk_size` (default: 500 characters), it is split on sentence boundaries (`[.!?]\s+`) with configurable sliding window overlap (default: 100 characters).
- **Small Fragment Merging**: Very short snippets (< 80 characters) are intelligently coalesced with preceding chunks to prevent micro-fragmentation.
- **Deterministic Numbering**: Generates stable chunk IDs formatted as `chunk_{document_id}_{index:03d}`.

---

## 4. Verification & Testing

The test suite in [`tests/test_chunking.py`](../../tests/test_chunking.py) verifies:
- `TestMarkdownLoader`: Single document loading, frontmatter parsing, fallback behavior for plain files, and directory batch loading (all 20 documents).
- `TestMetadataEnricher`: Access tier enum conversions, entity hint extraction across complex sentences.
- `TestSemanticChunker`: Chunk size enforcement, section breadcrumb preservation, overlap sliding, and end-to-end processing across the entire 20-document corpus.

Run the test suite:
```bash
./.venv/bin/pytest tests/test_chunking.py -v
```
All 8 tests pass with 100% success.
Total project test count: **22 passing tests**.
