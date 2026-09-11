"""Unit and integration tests for dense vector storage, embeddings, and semantic retrieval."""

import numpy as np
import pytest

from app.config import get_settings
from app.ingestion.chunker import DocumentChunk
from app.ingestion.metadata import AccessTier, ChunkMetadata
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.vector_retriever import VectorRetriever
from app.vector.embeddings import DefaultEmbeddingService, get_embedding_service
from app.vector.vector_store import QdrantVectorStore, get_vector_store


class TestEmbeddingService:
    """Tests for embedding generation, normalization, and fallback differentiation."""

    def test_embedding_dimensions_and_normalization(self) -> None:
        settings = get_settings()
        service = DefaultEmbeddingService(dimension=settings.embedding_dimension)
        text = "OAuth 2.1 protocol with PKCE verification and token rotation"

        vec = service.embed_text(text)
        assert len(vec) == settings.embedding_dimension
        norm = np.linalg.norm(np.array(vec))
        assert np.isclose(norm, 1.0, atol=1e-4)

    def test_batch_embedding_consistency(self) -> None:
        service = get_embedding_service()
        texts = [
            "Identity Service authentication architecture",
            "Redis cache cluster memory exhaustion incident",
        ]
        batch_vecs = service.embed_batch(texts)
        assert len(batch_vecs) == 2

        indiv_0 = service.embed_text(texts[0])
        indiv_1 = service.embed_text(texts[1])

        np.testing.assert_allclose(batch_vecs[0], indiv_0, atol=1e-5)
        np.testing.assert_allclose(batch_vecs[1], indiv_1, atol=1e-5)

    def test_empty_or_whitespace_embedding(self) -> None:
        service = get_embedding_service()
        v_empty = service.embed_text("")
        v_spaces = service.embed_text("   \n\t ")

        assert len(v_empty) == service.dimension
        assert np.isclose(np.linalg.norm(np.array(v_empty)), 1.0, atol=1e-4)
        assert len(v_spaces) == service.dimension

    def test_semantic_similarity_differentiation(self) -> None:
        service = get_embedding_service()
        t_auth1 = "OAuth 2.1 authentication flow and refresh token exchange"
        t_auth2 = "User authentication via OAuth token and credentials"
        t_infra = "Kubernetes container deployment with horizontal pod autoscaler"

        v_auth1 = np.array(service.embed_text(t_auth1))
        v_auth2 = np.array(service.embed_text(t_auth2))
        v_infra = np.array(service.embed_text(t_infra))

        sim_related = float(np.dot(v_auth1, v_auth2))
        sim_unrelated = float(np.dot(v_auth1, v_infra))

        assert sim_related > sim_unrelated
        assert sim_related > 0.15


class TestQdrantVectorStore:
    """Tests for Qdrant-backed vector storage, collection creation, and search."""

    @pytest.fixture
    def store(self) -> QdrantVectorStore:
        return QdrantVectorStore(in_memory=True, collection_name="test_vector_store")

    @pytest.fixture
    def sample_chunks(self) -> list[DocumentChunk]:
        chunk_1 = DocumentChunk(
            chunk_id="chunk_sec_001",
            document_id="service_identity",
            text="OAuth 2.1 deprecates implicit grant flow and requires PKCE for authorization code.",
            index=0,
            metadata=ChunkMetadata(
                document_id="service_identity",
                title="Identity Service Documentation",
                department="Security",
                access_tier=AccessTier.RESTRICTED,
                section_title="OAuth 2.1 Spec",
                section_path="Authentication > OAuth 2.1",
            ),
        )
        chunk_2 = DocumentChunk(
            chunk_id="chunk_ops_001",
            document_id="incident_inc402",
            text="Incident INC-402 occurred due to Redis cache memory saturation during Version 3.2 rollout.",
            index=0,
            metadata=ChunkMetadata(
                document_id="incident_inc402",
                title="Incident Report INC-402",
                department="Operations",
                access_tier=AccessTier.INTERNAL,
                section_title="Root Cause Analysis",
                section_path="Postmortem > Root Cause",
            ),
        )
        return [chunk_1, chunk_2]

    def test_in_memory_initialization_and_upsert(
        self, store: QdrantVectorStore, sample_chunks: list[DocumentChunk]
    ) -> None:
        assert store.count() == 0
        upserted = store.upsert_chunks(sample_chunks)
        assert upserted == 2
        assert store.count() == 2

    def test_idempotent_upsert(
        self, store: QdrantVectorStore, sample_chunks: list[DocumentChunk]
    ) -> None:
        store.upsert_chunks(sample_chunks)
        assert store.count() == 2
        # Upsert again with the same IDs
        store.upsert_chunks(sample_chunks)
        assert store.count() == 2

    def test_payload_preservation(
        self, store: QdrantVectorStore, sample_chunks: list[DocumentChunk]
    ) -> None:
        store.upsert_chunks(sample_chunks)
        service = get_embedding_service()
        query_vec = service.embed_text("OAuth 2.1 PKCE requirements")

        results = store.search(query_vec, top_k=1)
        assert len(results) == 1
        top = results[0]
        assert top.chunk_id == "chunk_sec_001"
        assert top.document_id == "service_identity"
        assert top.metadata["access_tier"] == "Restricted"
        assert top.metadata["section_title"] == "OAuth 2.1 Spec"

    def test_filtered_similarity_search(
        self, store: QdrantVectorStore, sample_chunks: list[DocumentChunk]
    ) -> None:
        store.upsert_chunks(sample_chunks)
        service = get_embedding_service()
        query_vec = service.embed_text("OAuth and Redis incidents")

        # Filter by document_id
        res_doc = store.search(query_vec, top_k=5, filters={"document_id": "incident_inc402"})
        assert len(res_doc) == 1
        assert res_doc[0].chunk_id == "chunk_ops_001"

        # Filter by access_tier
        res_tier = store.search(query_vec, top_k=5, filters={"access_tier": "Restricted"})
        assert len(res_tier) == 1
        assert res_tier[0].chunk_id == "chunk_sec_001"

    def test_clear_collection(
        self, store: QdrantVectorStore, sample_chunks: list[DocumentChunk]
    ) -> None:
        store.upsert_chunks(sample_chunks)
        assert store.count() == 2
        store.clear()
        assert store.count() == 0


class TestVectorRetriever:
    """Tests for VectorRetriever orchestration, rank assignment, and score calibration."""

    @pytest.fixture
    def retriever(self) -> VectorRetriever:
        store = QdrantVectorStore(in_memory=True, collection_name="test_retriever_store")
        chunk_1 = DocumentChunk(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="The Product Nova catalog relies on the Identity Service for secure OAuth access.",
            index=0,
            metadata=ChunkMetadata(
                document_id="doc_1",
                title="Product Nova Overview",
                access_tier=AccessTier.PUBLIC,
            ),
        )
        chunk_2 = DocumentChunk(
            chunk_id="chunk_2",
            document_id="doc_2",
            text="PostgreSQL relational database handles transactions, customer subscriptions, and billing.",
            index=0,
            metadata=ChunkMetadata(
                document_id="doc_2",
                title="Billing Database Manual",
                access_tier=AccessTier.INTERNAL,
            ),
        )
        store.upsert_chunks([chunk_1, chunk_2])
        return VectorRetriever(vector_store=store)

    def test_retrieve_ranked_chunks(self, retriever: VectorRetriever) -> None:
        results = retriever.retrieve("Product Nova authentication and Identity Service", top_k=2)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[0].score >= results[1].score
        assert results[0].chunk_id == "chunk_1"

    def test_empty_query_returns_empty_list(self, retriever: VectorRetriever) -> None:
        results = retriever.retrieve("   ")
        assert results == []

    def test_top_k_parameter(self, retriever: VectorRetriever) -> None:
        results = retriever.retrieve("database or identity", top_k=1)
        assert len(results) == 1


class TestPipelineVectorIntegration:
    """End-to-end integration test verifying full corpus ingestion populates vector store."""

    def test_full_corpus_vector_indexing(self) -> None:
        from app.graph.neo4j_client import get_graph_client

        graph_client = get_graph_client(force_in_memory=True)
        vector_store = QdrantVectorStore(in_memory=True, collection_name="test_pipeline_store")

        pipeline = IngestionPipeline(
            data_dir="data/documents",
            client=graph_client,
            vector_store=vector_store,
            index_vectors=True,
        )
        summary = pipeline.run()

        assert summary.documents_loaded == 20
        assert summary.chunks_created > 0
        assert summary.vector_points_indexed == summary.chunks_created
        assert vector_store.count() == summary.chunks_created

        # Run semantic search over ingested corpus
        retriever = VectorRetriever(vector_store=vector_store)
        results = retriever.retrieve("OAuth 2.1 implicit grant deprecation", top_k=3)
        assert len(results) == 3
        # Ensure at least one top result comes from identity or version changelog
        matching_docs = {r.document_id for r in results}
        assert any(doc in matching_docs for doc in ["service_identity", "version_history", "authentication"])
