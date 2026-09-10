"""Unit tests for the enterprise knowledge base document corpus."""

from pathlib import Path
import re
import pytest

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"

EXPECTED_DOCUMENTS = [
    "company_overview.md",
    "products.md",
    "product_nova.md",
    "product_orion.md",
    "product_atlas.md",
    "product_vega.md",
    "authentication.md",
    "authorization.md",
    "api_platform.md",
    "security.md",
    "data_privacy.md",
    "deployment.md",
    "billing.md",
    "pricing.md",
    "enterprise_customers.md",
    "customer_acme.md",
    "customer_globex.md",
    "customer_initech.md",
    "incident_response.md",
    "version_history.md",
]


class TestDocumentCorpus:
    """Test suite validating the integrity and multi-hop graph connectivity of documents."""

    def test_all_expected_documents_exist(self):
        assert DOCUMENTS_DIR.exists(), f"Directory {DOCUMENTS_DIR} does not exist"
        for doc_name in EXPECTED_DOCUMENTS:
            doc_path = DOCUMENTS_DIR / doc_name
            assert doc_path.exists(), f"Expected document missing: {doc_name}"
            assert doc_path.stat().st_size > 200, f"Document {doc_name} is suspiciously small"

    def test_frontmatter_metadata_structure(self):
        frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        required_keys = {"title", "document_id", "department", "access_tier", "version"}

        for doc_name in EXPECTED_DOCUMENTS:
            content = (DOCUMENTS_DIR / doc_name).read_text(encoding="utf-8")
            match = frontmatter_pattern.match(content)
            assert match is not None, f"Document {doc_name} is missing YAML frontmatter block"

            frontmatter_text = match.group(1)
            keys_found = {
                line.split(":", 1)[0].strip()
                for line in frontmatter_text.splitlines()
                if ":" in line and not line.strip().startswith("#")
            }
            missing_keys = required_keys - keys_found
            assert not missing_keys, f"Document {doc_name} missing required metadata keys: {missing_keys}"

    def test_multi_hop_cross_references(self):
        """Verify that core entities are referenced across multiple documents to ensure multi-hop traversability."""
        corpus = {doc: (DOCUMENTS_DIR / doc).read_text(encoding="utf-8") for doc in EXPECTED_DOCUMENTS}

        # Multi-hop Chain 1: Acme -> Nova -> Identity Service -> OAuth 2.1
        acme_docs = [doc for doc, text in corpus.items() if "Acme Corp" in text]
        nova_docs = [doc for doc, text in corpus.items() if "Product Nova" in text or "Nova" in text]
        identity_docs = [doc for doc, text in corpus.items() if "Identity Service" in text]
        oauth_docs = [doc for doc, text in corpus.items() if "OAuth 2.1" in text]

        assert len(acme_docs) >= 3, f"Acme Corp mentioned in too few documents: {acme_docs}"
        assert len(nova_docs) >= 5, f"Product Nova mentioned in too few documents: {nova_docs}"
        assert len(identity_docs) >= 4, f"Identity Service mentioned in too few documents: {identity_docs}"
        assert len(oauth_docs) >= 4, f"OAuth 2.1 mentioned in too few documents: {oauth_docs}"

        # Multi-hop Chain 2: Globex -> Orion / Atlas -> GDPR / Data Anonymization Service
        globex_docs = [doc for doc, text in corpus.items() if "Globex Corp" in text]
        orion_docs = [doc for doc, text in corpus.items() if "Product Orion" in text or "Orion" in text]
        anonymization_docs = [doc for doc, text in corpus.items() if "Data Anonymization Service" in text]

        assert len(globex_docs) >= 3, f"Globex Corp mentioned in too few documents: {globex_docs}"
        assert len(orion_docs) >= 5, f"Product Orion mentioned in too few documents: {orion_docs}"
        assert len(anonymization_docs) >= 3, f"Data Anonymization Service mentioned in too few documents: {anonymization_docs}"
