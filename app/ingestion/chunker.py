"""Semantic and structure-aware chunking for markdown documents."""

import re
from typing import Any
from pydantic import BaseModel, Field

from app.ingestion.loaders import LoadedDocument, MarkdownSection
from app.ingestion.metadata import ChunkMetadata, MetadataEnricher


class DocumentChunk(BaseModel):
    """A bounded semantic chunk derived from a document with rich contextual metadata."""

    chunk_id: str = Field(..., description="Stable deterministic chunk ID (e.g. chunk_product_nova_001)")
    document_id: str = Field(..., description="Parent document ID")
    text: str = Field(..., description="Text content of this chunk")
    index: int = Field(..., description="Sequential index of chunk within the document")
    metadata: ChunkMetadata = Field(..., description="Enriched metadata including section hierarchy and entity hints")


class SemanticChunker:
    """Structure-aware chunker that respects markdown sections, paragraphs, and sentence boundaries."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_size: int = 80,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.enricher = MetadataEnricher()

    def chunk_document(self, doc: LoadedDocument) -> list[DocumentChunk]:
        """Convert a LoadedDocument into an ordered list of DocumentChunks."""
        raw_chunks: list[tuple[str, MarkdownSection | None]] = []

        if doc.sections:
            for section in doc.sections:
                section_chunks = self._split_section(section.content)
                for chunk_text in section_chunks:
                    raw_chunks.append((chunk_text, section))
        else:
            # Fallback if no markdown sections were found
            doc_chunks = self._split_text_into_chunks(doc.content)
            for chunk_text in doc_chunks:
                raw_chunks.append((chunk_text, None))

        # Build DocumentChunk objects with sequential numbering
        results: list[DocumentChunk] = []
        for i, (text, section) in enumerate(raw_chunks, start=1):
            clean_text = text.strip()
            if not clean_text:
                continue

            chunk_id = f"chunk_{doc.document_id}_{i:03d}"
            sec_title = section.title if section else doc.title
            sec_path = section.path if section else doc.title

            meta = self.enricher.enrich(
                text=clean_text,
                document_id=doc.document_id,
                title=doc.title,
                department=doc.department,
                access_tier_str=doc.access_tier,
                version=doc.version,
                section_title=sec_title,
                section_path=sec_path,
                custom_metadata=doc.metadata,
            )

            results.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc.document_id,
                    text=clean_text,
                    index=i,
                    metadata=meta,
                )
            )

        return results

    def chunk_documents(self, docs: list[LoadedDocument]) -> list[DocumentChunk]:
        """Chunk an entire collection of LoadedDocument instances."""
        all_chunks: list[DocumentChunk] = []
        for doc in docs:
            all_chunks.extend(self.chunk_document(doc))
        return all_chunks

    def _split_section(self, section_content: str) -> list[str]:
        """Split a single section's text into size-bounded chunks, respecting paragraphs."""
        # Split into natural paragraphs or bullet lists
        paragraphs = re.split(r"\n\s*\n", section_content.strip())
        chunks: list[str] = []
        current_buffer: list[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_len = len(para)

            # If a single paragraph is larger than chunk_size, split it by sentences
            if para_len > self.chunk_size:
                # First flush accumulated buffer
                if current_buffer:
                    chunks.append("\n\n".join(current_buffer))
                    current_buffer = []
                    current_len = 0

                # Split large paragraph
                sub_chunks = self._split_large_paragraph(para)
                chunks.extend(sub_chunks)
                continue

            # If adding this paragraph exceeds target chunk size, flush buffer
            if current_len + para_len + 2 > self.chunk_size and current_buffer:
                chunks.append("\n\n".join(current_buffer))
                current_buffer = [para]
                current_len = para_len
            else:
                current_buffer.append(para)
                current_len += para_len + 2

        # Flush any remaining buffer
        if current_buffer:
            combined = "\n\n".join(current_buffer)
            # If buffer is tiny and we have previous chunks, merge with last if within bounds
            if len(combined) < self.min_chunk_size and chunks and len(chunks[-1]) + len(combined) + 2 <= self.chunk_size * 1.2:
                chunks[-1] = chunks[-1] + "\n\n" + combined
            else:
                chunks.append(combined)

        return chunks

    def _split_large_paragraph(self, paragraph: str) -> list[str]:
        """Split a long paragraph across sentence boundaries with sliding overlap."""
        # Regex to split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sent_len = len(sentence)
            if current_len + sent_len + 1 > self.chunk_size and current_chunk:
                chunk_str = " ".join(current_chunk)
                chunks.append(chunk_str)

                # Overlap: keep the last sentence(s) up to overlap limit
                overlap_buffer: list[str] = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) + 1 <= self.chunk_overlap:
                        overlap_buffer.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break

                current_chunk = overlap_buffer + [sentence]
                current_len = sum(len(s) + 1 for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_len += sent_len + 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """Fallback splitter for unstructured text."""
        return self._split_section(text)
