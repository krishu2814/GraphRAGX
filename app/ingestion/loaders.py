"""Document loaders for markdown files with YAML frontmatter parsing and section analysis."""

from pathlib import Path
import re
from typing import Any
from pydantic import BaseModel, Field


class MarkdownSection(BaseModel):
    """A semantic section within a document defined by markdown headings."""

    level: int = Field(..., ge=1, le=6, description="Heading level (1 for #, 2 for ##, etc.)")
    title: str = Field(..., description="Cleaned title text of the heading")
    content: str = Field(default="", description="Textual body belonging to this heading")
    path: str = Field(default="", description="Breadcrumb hierarchy path, e.g. Document > Section > Subsection")


class LoadedDocument(BaseModel):
    """A parsed document with extracted metadata, clean content, and structural sections."""

    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document display title")
    department: str = Field(default="General", description="Originating department or business unit")
    access_tier: str = Field(default="Internal", description="Classification tier (Public, Internal, Confidential)")
    version: str = Field(default="1.0", description="Associated product or policy version")
    last_updated: str = Field(default="", description="Date of last update")
    file_path: str = Field(default="", description="Source file location")
    content: str = Field(..., description="Clean markdown body (frontmatter stripped)")
    raw_text: str = Field(..., description="Raw text of the original file including frontmatter")
    sections: list[MarkdownSection] = Field(default_factory=list, description="Extracted structural sections")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary frontmatter key-values")


class MarkdownLoader:
    """Loads markdown documents and extracts YAML frontmatter, headers, and body text."""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def load_file(self, file_path: Path | str) -> LoadedDocument:
        """Load and parse a single markdown document from disk."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        raw_text = path.read_text(encoding="utf-8")
        frontmatter_data, body_content = self._extract_frontmatter(raw_text)

        # Fallback document_id from filename if not in frontmatter
        doc_id = frontmatter_data.get("document_id") or path.stem

        # Extract title from frontmatter or first H1 header or filename
        title = frontmatter_data.get("title") or self._extract_first_h1(body_content) or doc_id.replace("_", " ").title()

        # Parse section hierarchy
        sections = self._parse_sections(body_content, title)

        return LoadedDocument(
            document_id=doc_id,
            title=title,
            department=frontmatter_data.get("department", "General"),
            access_tier=frontmatter_data.get("access_tier", "Internal"),
            version=str(frontmatter_data.get("version", "1.0")),
            last_updated=str(frontmatter_data.get("last_updated", "")),
            file_path=str(path.resolve()),
            content=body_content.strip(),
            raw_text=raw_text,
            sections=sections,
            metadata=frontmatter_data,
        )

    def load_directory(self, dir_path: Path | str, pattern: str = "*.md") -> list[LoadedDocument]:
        """Load and parse all markdown documents matching pattern in a directory."""
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        documents: list[LoadedDocument] = []
        for file in sorted(path.glob(pattern)):
            if file.is_file():
                documents.append(self.load_file(file))
        return documents

    def _extract_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        """Extract YAML-like frontmatter key-value pairs and the remaining body."""
        match = self.FRONTMATTER_PATTERN.match(text)
        if not match:
            return {}, text

        frontmatter_str = match.group(1)
        body = text[match.end():]
        data: dict[str, Any] = {}

        for line in frontmatter_str.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            # Basic type coercions
            if val.lower() == "true":
                data[key] = True
            elif val.lower() == "false":
                data[key] = False
            else:
                data[key] = val

        return data, body

    def _extract_first_h1(self, text: str) -> str | None:
        """Find the first H1 header in markdown content."""
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_sections(self, body: str, root_title: str) -> list[MarkdownSection]:
        """Decompose markdown body into hierarchical sections based on headings."""
        sections: list[MarkdownSection] = []
        lines = body.splitlines()

        current_heading = root_title
        current_level = 1
        heading_stack: list[tuple[int, str]] = [(1, root_title)]
        current_lines: list[str] = []

        for line in lines:
            h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if h_match:
                # Flush previous section content
                content_str = "\n".join(current_lines).strip()
                if content_str:
                    path_str = " > ".join([h[1] for h in heading_stack])
                    sections.append(
                        MarkdownSection(
                            level=current_level,
                            title=current_heading,
                            content=content_str,
                            path=path_str,
                        )
                    )
                    current_lines = []

                # Update stack
                current_level = len(h_match.group(1))
                current_heading = h_match.group(2).strip()

                # Pop headings at equal or deeper level
                while heading_stack and heading_stack[-1][0] >= current_level:
                    heading_stack.pop()
                heading_stack.append((current_level, current_heading))
            else:
                current_lines.append(line)

        # Flush final section
        content_str = "\n".join(current_lines).strip()
        if content_str:
            path_str = " > ".join([h[1] for h in heading_stack])
            sections.append(
                MarkdownSection(
                    level=current_level,
                    title=current_heading,
                    content=content_str,
                    path=path_str,
                )
            )

        return sections
