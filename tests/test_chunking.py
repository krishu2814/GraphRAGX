"""Unit tests for document loading, semantic chunking, and metadata extraction."""

from pathlib import Path
import pytest

from app.ingestion.chunker import DocumentChunk, SemanticChunker
from app.ingestion.loaders import LoadedDocument, MarkdownLoader
from app.ingestion.metadata import AccessTier, MetadataEnricher

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"


class TestMarkdownLoader:
    """Test suite for MarkdownLoader."""

    def test_load_single_document_with_frontmatter(self):
        loader = MarkdownLoader()
        doc_path = DOCUMENTS_DIR / "product_nova.md"
        doc = loader.load_file(doc_path)

        assert doc.document_id == "product_nova"
        assert "Product Nova" in doc.title
        assert doc.department == "Engineering"
        assert doc.access_tier == "Internal"
        assert doc.version == "3.2"
        assert len(doc.sections) >= 2
        assert len(doc.content) > 100

    def test_load_file_without_frontmatter(self, tmp_path):
        plain_md = tmp_path / "simple_note.md"
        plain_md.write_text("# Simple Note\n\nThis is a simple paragraph.", encoding="utf-8")

        loader = MarkdownLoader()
        doc = loader.load_file(plain_md)

        assert doc.document_id == "simple_note"
        assert doc.title == "Simple Note"
        assert doc.department == "General"
        assert doc.access_tier == "Internal"
        assert doc.content == "# Simple Note\n\nThis is a simple paragraph."

    def test_load_entire_documents_directory(self):
        loader = MarkdownLoader()
        docs = loader.load_directory(DOCUMENTS_DIR)

        assert len(docs) == 20
        doc_ids = {d.document_id for d in docs}
        assert "company_overview" in doc_ids
        assert "customer_acme" in doc_ids
        assert "authentication" in doc_ids
        assert "incident_response" in doc_ids


class TestMetadataEnricher:
    """Test suite for metadata enrichment and entity hints."""

    def test_access_tier_normalization(self):
        assert AccessTier.from_str("public") == AccessTier.PUBLIC
        assert AccessTier.from_str("Internal") == AccessTier.INTERNAL
        assert AccessTier.from_str("CONFIDENTIAL") == AccessTier.CONFIDENTIAL
        assert AccessTier.from_str("restricted") == AccessTier.RESTRICTED
        assert AccessTier.from_str("unknown_value") == AccessTier.INTERNAL

    def test_detect_entity_hints(self):
        enricher = MetadataEnricher()
        text = (
            "Acme Corp deployed Product Nova on AWS using Identity Service for OAuth 2.1 authentication. "
            "Policy Engine evaluates all ABAC queries."
        )
        hints = enricher.detect_entity_hints(text)

        assert "Acme Corp" in hints
        assert "Product Nova" in hints
        assert "AWS" in hints
        assert "Identity Service" in hints
        assert "OAuth 2.1" in hints
        assert "Policy Engine" in hints
        assert "ABAC" in hints


class TestSemanticChunker:
    """Test suite for structure-aware semantic chunking."""

    def test_chunk_single_document(self):
        loader = MarkdownLoader()
        chunker = SemanticChunker(chunk_size=400, chunk_overlap=80)

        doc = loader.load_file(DOCUMENTS_DIR / "customer_acme.md")
        chunks = chunker.chunk_document(doc)

        assert len(chunks) >= 2
        for i, chunk in enumerate(chunks, start=1):
            assert chunk.document_id == "customer_acme"
            assert chunk.chunk_id == f"chunk_customer_acme_{i:03d}"
            assert chunk.index == i
            assert len(chunk.text) > 20
            assert chunk.metadata.document_id == "customer_acme"
            assert chunk.metadata.access_tier == AccessTier.CONFIDENTIAL
            assert chunk.metadata.section_path != ""
            assert chunk.metadata.estimated_tokens > 0

    def test_chunk_boundary_and_overlap(self):
        loader = MarkdownLoader()
        chunker = SemanticChunker(chunk_size=300, chunk_overlap=50)

        doc = loader.load_file(DOCUMENTS_DIR / "authentication.md")
        chunks = chunker.chunk_document(doc)

        assert len(chunks) >= 3
        # Check that chunk IDs are unique
        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_end_to_end_corpus_chunking(self):
        loader = MarkdownLoader()
        chunker = SemanticChunker(chunk_size=500, chunk_overlap=100)

        docs = loader.load_directory(DOCUMENTS_DIR)
        chunks = chunker.chunk_documents(docs)

        # 20 documents should yield roughly 40-70 total semantic chunks
        assert len(chunks) >= 35
        assert len(chunks) <= 100

        # Verify all chunks maintain entity hints
        chunks_with_hints = [c for c in chunks if len(c.metadata.entity_hints) > 0]
        # At least 90% of our enterprise chunks should contain domain entity hints
        assert len(chunks_with_hints) / len(chunks) >= 0.85
