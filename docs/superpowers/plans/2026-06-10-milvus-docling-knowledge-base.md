# Milvus Docling Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Chroma chunk-vector/text-loader RAG storage path with a Docling-based structured parser, SQLite document metadata tables, parent-child chunk model, pluggable embedding provider, Milvus vector index, and a left/right knowledge-base UI with upload support.

**Architecture:** Keep FastAPI route handlers thin and move business behavior into service classes. Use SQLite as the business metadata database with exactly two core tables, `document` and `document_chunk`; use Milvus as the vector index for child/table chunk vectors and filter metadata. Preserve the existing `/chat/stream` SSE contract while extending document APIs for upload, parse status, and knowledge-base browsing.

**Tech Stack:** FastAPI, Pydantic, Docling, OpenAI-compatible embeddings, pymilvus, SQLite via Python stdlib `sqlite3`, Next.js App Router, React, CSS in `frontend/app/globals.css`.

---

## File Structure

- Create `backend/app/models/document_models.py`: dataclasses/enums for `ParsedDocument`, `ParsedElement`, and `Chunk`.
- Create `backend/app/services/document_parser.py`: `DocumentParser` interface plus Docling parser and fallback parsers.
- Create `backend/app/services/document_chunker.py`: heading-first parent-child chunking and table embedding text generation.
- Create `backend/app/services/embedding_provider.py`: `EmbeddingProvider` interface plus OpenAI-compatible implementation.
- Create `backend/app/services/document_repository.py`: SQLite metadata persistence for `document` and `document_chunk`.
- Replace `backend/app/services/vector_store.py`: Milvus-backed vector store with the same high-level `upsert`, `query`, `count`, and reset-style responsibilities.
- Modify `backend/app/services/rag_service.py`: orchestrate upload, parse, persist, chunk, embed, index, hybrid retrieval, and parent recall using the new services.
- Modify `backend/app/main.py` and `backend/app/schemas.py`: wire new dependencies, env vars, and API response shapes.
- Modify `backend/requirements.txt`: add Docling and Milvus dependencies, remove Chroma when migration is complete.
- Modify `frontend/app/page.tsx` and `frontend/app/globals.css`: convert to left navigation plus chat/knowledge-base workspace.
- Update `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, `docs/design-docs/backend-rag-pipeline.md`, and `docs/design-docs/frontend-chat-ui.md`.

## Storage Boundary

This implementation uses the SQLite + Milvus split below. Do not keep Chroma as an active target store after the migration.

```text
SQLite:
  document
  document_chunk

Milvus:
  chunk vector
```

- SQLite owns all durable business records: document identity, file metadata, parse status, parent chunks, child chunks, table chunks, full text, Markdown, page ranges, title paths, token counts, and JSON metadata.
- Milvus owns only vector-search records for `child` and `table` chunks: embedding vector plus `chunk_id`, `doc_id`, `parent_id`, `chunk_type`, `title_path`, `page_start`, and `page_end`.
- Chroma is the legacy implementation being replaced. `backend/chroma_db/` must be left untouched during migration unless the user explicitly requests cleanup.
- Retrieval flow is Milvus hit -> `chunk_id`/`parent_id` -> SQLite `document_chunk` lookup -> parent context assembly.

## Table Handling

Tables must be treated as first-class RAG content, not split into arbitrary text fragments.

- Preserve each table as one `table` chunk whenever possible. Do not split table rows across multiple chunks unless the table exceeds the model context budget by itself.
- Save table title, nearby pre/post explanatory text, raw Markdown, raw HTML, page range, and title path in SQLite `document_chunk`.
- Generate a table `summary` for retrieval metadata from caption, column names, nearby explanation, and representative row values. Example summary: `该表描述服务器资源规格，包括 CPU、内存、GPU 数量等字段。CPU 为 Kunpeng 920，内存为 32*64GB，GPU 为 8 卡。`
- Build `embedding_text` as `title_path + caption + summary + content_markdown`, so vector retrieval can match both semantic descriptions and exact table terms.
- Build `llm_context` from the original Markdown/HTML table plus caption and nearby explanation, so generation keeps table structure.

Required table chunk shape:

```json
{
  "chunk_id": "table_001",
  "parent_id": "parent_003",
  "type": "table",
  "title_path": "第4章 / 资源规格",
  "caption": "表4-1 服务器规格",
  "content_markdown": "| CPU | 内存 | GPU |\n|---|---|---|\n| Kunpeng 920 | 32*64GB | 8卡 |",
  "page": 22
}
```

## Task 1: Domain Models For Parsed Documents And Chunks

**Files:**
- Create: `backend/app/models/document_models.py`
- Create: `backend/tests/test_document_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from app.models.document_models import Chunk, ParsedDocument, ParsedElement


def test_parsed_document_contains_required_element_fields():
    element = ParsedElement(
        element_id="el-1",
        type="title",
        text="安装说明",
        markdown="# 安装说明",
        html="<h1>安装说明</h1>",
        page_start=1,
        page_end=1,
        level=1,
        title_path="安装说明",
        metadata={"source": "docling"},
    )
    parsed = ParsedDocument(
        doc_id="doc-1",
        file_name="manual.pdf",
        file_type="pdf",
        elements=[element],
    )

    assert parsed.doc_id == "doc-1"
    assert parsed.elements[0].type == "title"
    assert parsed.elements[0].title_path == "安装说明"


def test_chunk_has_embedding_text_context():
    chunk = Chunk(
        id="chunk-1",
        doc_id="doc-1",
        parent_id="parent-1",
        chunk_type="child",
        title_path="安装说明/准备工作",
        content="安装前请确认环境。",
        content_markdown="安装前请确认环境。",
        page_start=2,
        page_end=2,
        token_count=12,
        metadata={},
    )

    assert "安装说明/准备工作" in chunk.embedding_text
    assert "安装前请确认环境" in chunk.embedding_text
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_models.py -v
```

Expected: FAIL because `app.models.document_models` does not exist.

- [ ] **Step 3: Implement the models**

Create `backend/app/models/document_models.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Literal

ElementType = Literal["title", "paragraph", "table", "image", "list", "code", "unknown"]
ChunkType = Literal["parent", "child", "table", "summary"]


@dataclass(frozen=True)
class ParsedElement:
    element_id: str
    type: ElementType
    text: str
    markdown: str
    html: str
    page_start: int | None
    page_end: int | None
    level: int | None
    title_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    doc_id: str
    file_name: str
    file_type: str
    elements: list[ParsedElement]


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    parent_id: str | None
    chunk_type: ChunkType
    title_path: str
    content: str
    content_markdown: str
    page_start: int | None
    page_end: int | None
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def embedding_text(self) -> str:
        pieces = [self.title_path.strip(), self.content.strip()]
        caption = str(self.metadata.get("caption", "")).strip()
        summary = str(self.metadata.get("summary", "")).strip()
        fields = self.metadata.get("fields", [])
        if caption:
            pieces.append(caption)
        if summary:
            pieces.append(summary)
        if fields:
            pieces.append("字段: " + ", ".join(str(field) for field in fields))
        return "\n".join(piece for piece in pieces if piece)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/document_models.py backend/tests/test_document_models.py
git commit -m "feat: add document parsing domain models"
```

## Task 2: DocumentParser Interface And Docling Parser

**Files:**
- Create: `backend/app/services/document_parser.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_document_parser.py`

- [ ] **Step 1: Write parser tests with monkeypatched Docling output**

```python
from pathlib import Path
from types import SimpleNamespace

from app.services.document_parser import DoclingDocumentParser, get_parser_for_path


def test_get_parser_accepts_requested_types(tmp_path):
    for name in ["a.pdf", "b.docx", "c.html", "d.xlsx", "e.md"]:
        path = tmp_path / name
        path.write_text("x", encoding="utf-8")
        assert get_parser_for_path(path) is not None


def test_docling_parser_normalizes_elements(monkeypatch, tmp_path):
    file_path = tmp_path / "manual.pdf"
    file_path.write_bytes(b"%PDF")

    class FakeResult:
        document = SimpleNamespace(
            export_to_markdown=lambda: "# 标题\n\n正文",
            export_to_html=lambda: "<h1>标题</h1><p>正文</p>",
        )

    class FakeConverter:
        def convert(self, path):
            assert Path(path) == file_path
            return FakeResult()

    monkeypatch.setattr("app.services.document_parser.DocumentConverter", lambda: FakeConverter())

    parsed = DoclingDocumentParser().parse(file_path)

    assert parsed.file_name == "manual.pdf"
    assert parsed.file_type == "pdf"
    assert parsed.elements
    assert parsed.elements[0].type == "title"
    assert parsed.elements[0].title_path == "标题"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_parser.py -v
```

Expected: FAIL because `document_parser.py` does not exist.

- [ ] **Step 3: Add dependencies**

Modify `backend/requirements.txt` to include:

```text
docling
beautifulsoup4==4.12.3
```

Keep existing PDF/DOCX/Excel packages until fallback parsing has been verified.

- [ ] **Step 4: Implement parser interface and normalization**

Create `backend/app/services/document_parser.py` with:

```python
import hashlib
import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from bs4 import BeautifulSoup
from docling.document_converter import DocumentConverter

from app.models.document_models import ParsedDocument, ParsedElement

SUPPORTED_PARSE_EXTS = {".pdf", ".docx", ".html", ".htm", ".xlsx", ".xlsm", ".xls", ".md", ".markdown"}


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        raise NotImplementedError


class DoclingDocumentParser(DocumentParser):
    def parse(self, file_path: Path) -> ParsedDocument:
        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown = result.document.export_to_markdown() or ""
        html = result.document.export_to_html() or ""
        elements = _elements_from_markdown_and_html(markdown, html)
        doc_id = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[:32]
        return ParsedDocument(
            doc_id=doc_id,
            file_name=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            elements=elements,
        )


def get_parser_for_path(file_path: Path) -> DocumentParser:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_PARSE_EXTS:
        raise ValueError(f"Unsupported document type: {suffix}")
    return DoclingDocumentParser()


def _elements_from_markdown_and_html(markdown: str, html: str) -> list[ParsedElement]:
    soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")
    html_blocks = [str(tag) for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "li", "pre"])]
    elements: list[ParsedElement] = []
    title_stack: list[str] = []
    html_index = 0

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        element_type = "paragraph"
        level = None
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            title_stack = title_stack[: level - 1] + [text]
            element_type = "title"
        elif line.startswith("|") and line.endswith("|"):
            text = line
            element_type = "table"
        elif re.match(r"^[-*+]\s+", line) or re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^([-*+]|\d+\.)\s+", "", line)
            element_type = "list"
        else:
            text = line

        element_html = html_blocks[html_index] if html_index < len(html_blocks) else ""
        html_index += 1
        elements.append(
            ParsedElement(
                element_id=f"el-{uuid4().hex}",
                type=element_type,
                text=text,
                markdown=line,
                html=element_html,
                page_start=None,
                page_end=None,
                level=level,
                title_path="/".join(title_stack),
                metadata={},
            )
        )
    return elements
```

- [ ] **Step 5: Run parser tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_parser.py -v
```

Expected: PASS. If dependency install is missing, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` first.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/document_parser.py backend/tests/test_document_parser.py backend/requirements.txt
git commit -m "feat: add docling document parser abstraction"
```

## Task 3: Heading-First Parent-Child Chunker

**Files:**
- Create: `backend/app/services/document_chunker.py`
- Create: `backend/tests/test_document_chunker.py`

- [ ] **Step 1: Write chunker tests**

```python
from app.models.document_models import ParsedDocument, ParsedElement
from app.services.document_chunker import DocumentChunker


def element(idx, type, text, title_path, level=None, markdown=None, page=1):
    return ParsedElement(
        element_id=f"el-{idx}",
        type=type,
        text=text,
        markdown=markdown or text,
        html="",
        page_start=page,
        page_end=page,
        level=level,
        title_path=title_path,
        metadata={},
    )


def test_chunker_creates_parent_and_child_chunks_by_heading():
    parsed = ParsedDocument(
        doc_id="doc-1",
        file_name="manual.md",
        file_type="md",
        elements=[
            element(1, "title", "第一章", "第一章", level=1),
            element(2, "paragraph", "段落一。" * 80, "第一章"),
            element(3, "paragraph", "段落二。" * 80, "第一章"),
        ],
    )

    chunks = DocumentChunker(parent_max_tokens=300, child_max_tokens=80, child_overlap_tokens=10).chunk(parsed)

    parents = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
    children = [chunk for chunk in chunks if chunk.chunk_type == "child"]
    assert parents
    assert children
    assert all(child.parent_id in {parent.id for parent in parents} for child in children)
    assert children[0].title_path == "第一章"


def test_table_chunk_preserves_markdown_html_and_builds_embedding_text():
    parsed = ParsedDocument(
        doc_id="doc-1",
        file_name="manual.md",
        file_type="md",
        elements=[
            element(1, "title", "第4章", "第4章", level=1),
            element(2, "title", "资源规格", "第4章 / 资源规格", level=2),
            element(3, "paragraph", "下表列出服务器资源规格。", "第4章 / 资源规格"),
            ParsedElement(
                element_id="el-4",
                type="table",
                text="CPU 内存 GPU\nKunpeng 920 32*64GB 8卡",
                markdown="| CPU | 内存 | GPU |\n|---|---|---|\n| Kunpeng 920 | 32*64GB | 8卡 |",
                html="<table><tr><th>CPU</th><th>内存</th><th>GPU</th></tr><tr><td>Kunpeng 920</td><td>32*64GB</td><td>8卡</td></tr></table>",
                page_start=22,
                page_end=22,
                level=None,
                title_path="第4章 / 资源规格",
                metadata={"caption": "表4-1 服务器规格"},
            ),
        ],
    )

    chunks = DocumentChunker().chunk(parsed)
    table_chunks = [chunk for chunk in chunks if chunk.chunk_type == "table"]

    assert len(table_chunks) == 1
    assert table_chunks[0].parent_id is not None
    assert table_chunks[0].title_path == "第4章 / 资源规格"
    assert table_chunks[0].metadata["caption"] == "表4-1 服务器规格"
    assert "| Kunpeng 920 | 32*64GB | 8卡 |" in table_chunks[0].content_markdown
    assert "fields" in table_chunks[0].metadata
    assert "CPU" in table_chunks[0].metadata["fields"]
    assert "服务器资源规格" in table_chunks[0].metadata["summary"]
    assert "<table>" in table_chunks[0].metadata["llm_context"]
    assert "表4-1 服务器规格" in table_chunks[0].embedding_text
    assert "Kunpeng 920" in table_chunks[0].embedding_text
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_chunker.py -v
```

Expected: FAIL because `DocumentChunker` does not exist.

- [ ] **Step 3: Implement chunker**

Create `backend/app/services/document_chunker.py` with:

```python
from uuid import uuid4

from app.models.document_models import Chunk, ParsedDocument, ParsedElement


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class DocumentChunker:
    def __init__(
        self,
        parent_max_tokens: int = 2400,
        child_max_tokens: int = 600,
        child_overlap_tokens: int = 80,
    ):
        self.parent_max_tokens = parent_max_tokens
        self.child_max_tokens = child_max_tokens
        self.child_overlap_tokens = child_overlap_tokens

    def chunk(self, parsed: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        sections = self._group_sections(parsed.elements)
        for section_index, section_elements in enumerate(sections):
            chunks.extend(self._chunk_section(parsed.doc_id, section_index, section_elements))
        return chunks

    def _group_sections(self, elements: list[ParsedElement]) -> list[list[ParsedElement]]:
        sections: list[list[ParsedElement]] = []
        current: list[ParsedElement] = []
        for element in elements:
            if element.type == "title" and element.level in {1, 2} and current:
                sections.append(current)
                current = [element]
            else:
                current.append(element)
        if current:
            sections.append(current)
        return sections

    def _chunk_section(self, doc_id: str, section_index: int, elements: list[ParsedElement]) -> list[Chunk]:
        chunks: list[Chunk] = []
        content = "\n".join(element.text for element in elements if element.text).strip()
        markdown = "\n\n".join(element.markdown for element in elements if element.markdown).strip()
        title_path = next((element.title_path for element in elements if element.title_path), "")
        page_start = min((element.page_start for element in elements if element.page_start is not None), default=None)
        page_end = max((element.page_end for element in elements if element.page_end is not None), default=None)

        parent_parts = self._split_text_by_token_limit(content, self.parent_max_tokens)
        for parent_part_index, parent_text in enumerate(parent_parts):
            parent_id = f"{doc_id}::parent-{section_index}-{parent_part_index}"
            parent_chunk = Chunk(
                id=parent_id,
                doc_id=doc_id,
                parent_id=None,
                chunk_type="parent",
                title_path=title_path,
                content=parent_text,
                content_markdown=markdown if parent_part_index == 0 else parent_text,
                page_start=page_start,
                page_end=page_end,
                token_count=estimate_tokens(parent_text),
                metadata={"section_index": section_index},
            )
            chunks.append(parent_chunk)
            chunks.extend(self._child_chunks_for_parent(doc_id, parent_id, title_path, parent_text, page_start, page_end))

        for element in elements:
            if element.type == "table":
                chunks.append(self._table_chunk(doc_id, chunks, title_path, element, elements, page_start, page_end))
        return chunks

    def _child_chunks_for_parent(self, doc_id: str, parent_id: str, title_path: str, text: str, page_start, page_end) -> list[Chunk]:
        parts = self._split_text_by_token_limit(text, self.child_max_tokens, self.child_overlap_tokens)
        return [
            Chunk(
                id=f"{parent_id}::child-{idx}",
                doc_id=doc_id,
                parent_id=parent_id,
                chunk_type="child",
                title_path=title_path,
                content=part,
                content_markdown=part,
                page_start=page_start,
                page_end=page_end,
                token_count=estimate_tokens(part),
                metadata={"child_index": idx},
            )
            for idx, part in enumerate(parts)
            if part.strip()
        ]

    def _table_chunk(self, doc_id: str, existing_chunks: list[Chunk], title_path: str, element: ParsedElement, section_elements: list[ParsedElement], page_start, page_end) -> Chunk:
        parent_candidates = [chunk for chunk in existing_chunks if chunk.chunk_type == "parent"]
        parent_id = parent_candidates[-1].id if parent_candidates else f"{doc_id}::parent-table-{uuid4().hex[:8]}"
        fields = [cell.strip() for cell in element.markdown.splitlines()[0].strip("|").split("|")] if element.markdown else []
        caption = str(element.metadata.get("caption", "")).strip()
        nearby_text = self._nearby_table_text(section_elements, element.element_id)
        summary = self._summarize_table(caption, nearby_text, fields, element.text)
        llm_context = "\n\n".join(part for part in [caption, nearby_text, element.markdown, element.html] if part)
        return Chunk(
            id=f"{parent_id}::table-{uuid4().hex[:8]}",
            doc_id=doc_id,
            parent_id=parent_id,
            chunk_type="table",
            title_path=title_path,
            content=element.text,
            content_markdown=element.markdown,
            page_start=element.page_start or page_start,
            page_end=element.page_end or page_end,
            token_count=estimate_tokens(element.text),
            metadata={
                "caption": caption,
                "fields": fields,
                "nearby_text": nearby_text,
                "summary": summary,
                "llm_context": llm_context,
                "html": element.html,
            },
        )

    def _nearby_table_text(self, section_elements: list[ParsedElement], table_element_id: str) -> str:
        table_index = next((idx for idx, item in enumerate(section_elements) if item.element_id == table_element_id), -1)
        if table_index < 0:
            return ""
        nearby = []
        for idx in [table_index - 1, table_index + 1]:
            if 0 <= idx < len(section_elements) and section_elements[idx].type in {"paragraph", "list"}:
                nearby.append(section_elements[idx].text)
        return "\n".join(text for text in nearby if text)

    def _summarize_table(self, caption: str, nearby_text: str, fields: list[str], table_text: str) -> str:
        field_text = "、".join(field for field in fields if field)
        sample = " ".join(table_text.split())[:300]
        return "。".join(part for part in [caption, nearby_text, f"字段包括 {field_text}" if field_text else "", sample] if part)

    def _split_text_by_token_limit(self, text: str, max_tokens: int, overlap_tokens: int = 0) -> list[str]:
        words = text.split()
        if not words:
            return [text] if text else []
        max_chars = max_tokens * 4
        overlap_chars = overlap_tokens * 4
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            parts.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(0, end - overlap_chars)
        return [part for part in parts if part]
```

- [ ] **Step 4: Run chunker tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_chunker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/document_chunker.py backend/tests/test_document_chunker.py
git commit -m "feat: add structured parent child chunker"
```

## Task 4: EmbeddingProvider Interface

**Files:**
- Create: `backend/app/services/embedding_provider.py`
- Create: `backend/tests/test_embedding_provider.py`

- [ ] **Step 1: Write provider tests**

```python
from types import SimpleNamespace

from app.services.embedding_provider import OpenAIEmbeddingProvider


class FakeEmbeddings:
    def create(self, model, input):
        if isinstance(input, str):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0])])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[float(i), 2.0]) for i, _ in enumerate(input)])


class FakeClient:
    embeddings = FakeEmbeddings()


def test_embed_text_uses_configured_model():
    provider = OpenAIEmbeddingProvider(client=FakeClient(), model="test-model")
    assert provider.embed_text("hello") == [1.0, 2.0]


def test_embed_batch_returns_vectors_in_order():
    provider = OpenAIEmbeddingProvider(client=FakeClient(), model="test-model")
    assert provider.embed_batch(["a", "b"]) == [[0.0, 2.0], [1.0, 2.0]]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_embedding_provider.py -v
```

Expected: FAIL because `embedding_provider.py` does not exist.

- [ ] **Step 3: Implement provider**

Create `backend/app/services/embedding_provider.py`:

```python
from abc import ABC, abstractmethod

from openai import OpenAI


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def embed_text(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [list(item.embedding) for item in response.data]
```

- [ ] **Step 4: Run provider tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_embedding_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/embedding_provider.py backend/tests/test_embedding_provider.py
git commit -m "feat: add embedding provider abstraction"
```

## Task 5: SQLite Document Repository

**Files:**
- Create: `backend/app/services/document_repository.py`
- Create: `backend/tests/test_document_repository.py`

- [ ] **Step 1: Write repository tests**

```python
from pathlib import Path

from app.models.document_models import Chunk
from app.services.document_repository import DocumentRepository


def test_repository_saves_document_and_chunks(tmp_path):
    repo = DocumentRepository(tmp_path / "rag.sqlite3")
    repo.upsert_document(
        id="doc-1",
        name="manual.pdf",
        file_type="pdf",
        storage_path="uploads/manual.pdf",
        parse_status="parsed",
        metadata_json={"page_count": 2},
    )
    repo.replace_chunks(
        "doc-1",
        [
            Chunk(
                id="parent-1",
                doc_id="doc-1",
                parent_id=None,
                chunk_type="parent",
                title_path="章",
                content="完整上下文",
                content_markdown="完整上下文",
                page_start=1,
                page_end=1,
                token_count=10,
                metadata={},
            )
        ],
    )

    docs = repo.list_documents()
    assert docs[0]["id"] == "doc-1"
    assert docs[0]["parse_status"] == "parsed"
    assert repo.get_chunk("parent-1")["content"] == "完整上下文"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_repository.py -v
```

Expected: FAIL because `DocumentRepository` does not exist.

- [ ] **Step 3: Implement repository and schema**

Create `backend/app/services/document_repository.py`:

```python
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.document_models import Chunk


class DocumentRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists document (
                    id text primary key,
                    name text not null,
                    file_type text not null,
                    storage_path text not null,
                    parse_status text not null,
                    created_at text not null,
                    updated_at text not null,
                    metadata_json text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists document_chunk (
                    id text primary key,
                    doc_id text not null,
                    parent_id text,
                    chunk_type text not null,
                    title_path text not null,
                    content text not null,
                    content_markdown text not null,
                    page_start integer,
                    page_end integer,
                    token_count integer not null,
                    metadata_json text not null,
                    created_at text not null
                )
                """
            )

    def upsert_document(self, id: str, name: str, file_type: str, storage_path: str, parse_status: str, metadata_json: dict[str, Any]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            existing = conn.execute("select created_at from document where id = ?", (id,)).fetchone()
            created_at = existing[0] if existing else now
            conn.execute(
                """
                insert or replace into document
                (id, name, file_type, storage_path, parse_status, created_at, updated_at, metadata_json)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (id, name, file_type, storage_path, parse_status, created_at, now, json.dumps(metadata_json, ensure_ascii=False)),
            )

    def replace_chunks(self, doc_id: str, chunks: list[Chunk]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute("delete from document_chunk where doc_id = ?", (doc_id,))
            conn.executemany(
                """
                insert into document_chunk
                (id, doc_id, parent_id, chunk_type, title_path, content, content_markdown, page_start, page_end, token_count, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.doc_id,
                        chunk.parent_id,
                        chunk.chunk_type,
                        chunk.title_path,
                        chunk.content,
                        chunk.content_markdown,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.token_count,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        now,
                    )
                    for chunk in chunks
                ],
            )

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select d.*, count(c.id) as chunks
                from document d
                left join document_chunk c on c.doc_id = d.id
                group by d.id
                order by d.updated_at desc
                """
            ).fetchall()
        return [dict(row) | {"metadata_json": json.loads(row["metadata_json"])} for row in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from document_chunk where id = ?", (chunk_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["metadata_json"] = json.loads(data["metadata_json"])
        return data
```

- [ ] **Step 4: Run repository tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_repository.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/document_repository.py backend/tests/test_document_repository.py
git commit -m "feat: add document metadata repository"
```

## Task 6: Milvus Vector Store

**Files:**
- Replace: `backend/app/services/vector_store.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_milvus_vector_store.py`

- [ ] **Step 1: Write vector-store tests using a fake Milvus collection**

```python
from app.models.document_models import Chunk
from app.services.vector_store import MilvusVectorStore


class FakeProvider:
    def embed_text(self, text):
        return [0.1, 0.2]

    def embed_batch(self, texts):
        return [[float(i), 0.2] for i, _ in enumerate(texts)]


def test_vector_store_indexes_only_child_and_table_chunks(monkeypatch):
    inserted = []

    class FakeCollection:
        def insert(self, rows):
            inserted.extend(rows)

        def flush(self):
            pass

        def num_entities(self):
            return len(inserted)

    monkeypatch.setattr("app.services.vector_store._create_or_load_collection", lambda *args, **kwargs: FakeCollection())

    store = MilvusVectorStore(uri="fake", collection_name="rag_chunk_vectors", embedding_dim=2, embedding_provider=FakeProvider())
    chunks = [
        Chunk("p1", "doc-1", None, "parent", "章", "parent", "parent", 1, 1, 1, {}),
        Chunk("c1", "doc-1", "p1", "child", "章", "child", "child", 1, 1, 1, {}),
        Chunk("t1", "doc-1", "p1", "table", "章", "table", "| A |", 1, 1, 1, {"fields": ["A"]}),
    ]

    store.upsert_chunks(chunks)

    assert len(inserted) == 2
    assert {row["chunk_type"] for row in inserted} == {"child", "table"}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_milvus_vector_store.py -v
```

Expected: FAIL because `MilvusVectorStore` does not exist.

- [ ] **Step 3: Add Milvus dependency**

Modify `backend/requirements.txt`:

```text
pymilvus==2.5.4
```

Remove `chromadb==0.5.23` only after Task 10 verification passes.

- [ ] **Step 4: Implement Milvus store**

Replace `backend/app/services/vector_store.py` with a Milvus-backed class that exposes:

```python
class MilvusVectorStore:
    def __init__(self, uri: str, collection_name: str, embedding_dim: int, embedding_provider: EmbeddingProvider): ...
    def reset_collection(self) -> None: ...
    def upsert_chunks(self, chunks: list[Chunk]) -> None: ...
    def query(self, question: str, top_k: int) -> list[dict[str, Any]]: ...
    def count(self) -> int: ...
```

Milvus fields:

```text
id VarChar primary key
embedding FloatVector
chunk_id VarChar
doc_id VarChar
parent_id VarChar
chunk_type VarChar
title_path VarChar
page_start Int64
page_end Int64
```

Embedding input rule:

```text
child chunk -> chunk.embedding_text
table chunk -> title_path + caption + summary + content_markdown
```

For compatibility during migration, also implement:

```python
def upsert(self, ids: list[str], docs: list[str], metadatas: list[dict[str, Any]]) -> None:
    raise RuntimeError("Use upsert_chunks with structured Chunk objects")
```

- [ ] **Step 5: Run vector-store tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_milvus_vector_store.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/vector_store.py backend/tests/test_milvus_vector_store.py backend/requirements.txt
git commit -m "feat: add milvus vector store"
```

## Task 7: RAGService Migration To Parser, Chunker, Repository, Milvus

**Files:**
- Modify: `backend/app/services/rag_service.py`
- Create: `backend/tests/test_rag_service_structured_ingest.py`

- [ ] **Step 1: Write service orchestration tests**

```python
from pathlib import Path
from types import SimpleNamespace

from app.models.document_models import Chunk, ParsedDocument, ParsedElement
from app.services.rag_service import RAGService


class FakeRepository:
    def __init__(self):
        self.documents = []
        self.chunks = []

    def upsert_document(self, **kwargs):
        self.documents.append(kwargs)

    def replace_chunks(self, doc_id, chunks):
        self.chunks = chunks

    def list_documents(self):
        return self.documents

    def get_chunk(self, chunk_id):
        for chunk in self.chunks:
            if chunk.id == chunk_id:
                return {"id": chunk.id, "content": chunk.content, "metadata_json": chunk.metadata}
        return None


class FakeParser:
    def parse(self, file_path):
        return ParsedDocument(
            doc_id="doc-1",
            file_name=file_path.name,
            file_type=file_path.suffix.lstrip("."),
            elements=[
                ParsedElement("e1", "title", "章", "# 章", "", 1, 1, 1, "章", {}),
                ParsedElement("e2", "paragraph", "正文", "正文", "", 1, 1, None, "章", {}),
            ],
        )


class FakeChunker:
    def chunk(self, parsed):
        return [
            Chunk("p1", parsed.doc_id, None, "parent", "章", "完整上下文", "完整上下文", 1, 1, 10, {}),
            Chunk("c1", parsed.doc_id, "p1", "child", "章", "正文", "正文", 1, 1, 3, {}),
        ]


class FakeVectorStore:
    persist_dir = Path(".")

    def __init__(self):
        self.indexed = []

    def upsert_chunks(self, chunks):
        self.indexed = chunks

    def count(self):
        return len(self.indexed)


def test_parse_and_index_document_persists_parent_and_indexes_child(tmp_path):
    repo = FakeRepository()
    vector = FakeVectorStore()
    service = RAGService(
        vector_store=vector,
        llm_client=SimpleNamespace(),
        chat_model="test",
        system_prompt="test",
        data_dir=str(tmp_path),
        top_k=3,
        min_relevance_score=0.0,
        chunk_size=600,
        chunk_overlap=80,
        document_repository=repo,
        document_parser=FakeParser(),
        document_chunker=FakeChunker(),
    )
    file_path = tmp_path / "manual.md"
    file_path.write_text("# 章\n正文", encoding="utf-8")

    result = service.parse_and_index_document(file_path)

    assert result["doc_id"] == "doc-1"
    assert repo.chunks[0].chunk_type == "parent"
    assert vector.indexed[0].chunk_type == "child"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_rag_service_structured_ingest.py -v
```

Expected: FAIL because `RAGService` constructor does not accept the new collaborators.

- [ ] **Step 3: Refactor service constructor**

Add optional constructor parameters:

```python
document_repository: DocumentRepository
document_parser: DocumentParser
document_chunker: DocumentChunker
```

Keep `top_k`, `min_relevance_score`, `system_prompt`, and streaming behavior unchanged.

- [ ] **Step 4: Add `parse_and_index_document`**

Implement behavior:

```text
1. Upsert document with parse_status="parsing".
2. Run parser.parse(file_path).
3. Run chunker.chunk(parsed).
4. repository.replace_chunks(parsed.doc_id, chunks).
5. vector_store.upsert_chunks(chunks where chunk_type is child/table).
6. Upsert document with parse_status="parsed".
7. On exception, upsert parse_status="failed" with error_message in metadata_json and re-raise.
```

- [ ] **Step 5: Update retrieval**

Change parent recall to:

```text
Milvus hit metadata -> parent_id -> document_repository.get_chunk(parent_id) -> parent content_markdown
```

For `table` hits, use `metadata_json.llm_context` as the first LLM context candidate. If `llm_context` is missing, fall back to `content_markdown`, then `content`.

Keep keyword/BM25 simple for this implementation by building a keyword scan over repository child/table chunks. Do not keep `parent_store.json` and `keyword_index.json` as source of truth.

- [ ] **Step 6: Run service tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_rag_service_structured_ingest.py tests/test_hybrid_retrieval.py -v
```

Expected: PASS after adapting legacy hybrid tests to repository-backed parent recall.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/rag_service.py backend/tests/test_rag_service_structured_ingest.py backend/tests/test_hybrid_retrieval.py
git commit -m "feat: migrate rag service to structured ingest"
```

## Task 8: API Schemas And Backend Wiring

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_knowledge_base.py`

- [ ] **Step 1: Write API schema tests**

```python
from app.schemas import DocumentItem, DocumentUploadResponse


def test_document_item_includes_parse_status_and_doc_id():
    item = DocumentItem(
        id="doc-1",
        name="manual.pdf",
        file_type="pdf",
        storage_path="uploads/manual.pdf",
        parse_status="parsed",
        created_at="2026-06-10T10:00:00",
        updated_at="2026-06-10T10:00:00",
        chunks=3,
        metadata_json={},
    )

    assert item.id == "doc-1"
    assert item.parse_status == "parsed"


def test_upload_response_returns_doc_id():
    response = DocumentUploadResponse(doc_id="doc-1", source="uploads/manual.pdf", filename="manual.pdf", size=10)
    assert response.doc_id == "doc-1"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_api_knowledge_base.py -v
```

Expected: FAIL because schemas do not include new fields.

- [ ] **Step 3: Update schemas**

Update `DocumentUploadResponse`, `DocumentParseResponse`, `DocumentItem`, and `DocumentsResponse` to include `doc_id`, parse status, file type, chunk counts by type, and metadata JSON.

- [ ] **Step 4: Wire services in `main.py`**

Read env vars:

```text
METADATA_DB_PATH=./vector_db/rag_metadata.sqlite3
MILVUS_URI=http://127.0.0.1:19530
MILVUS_TOKEN=root:Milvus
MILVUS_COLLECTION=rag_chunk_vectors
EMBEDDING_PROVIDER=openai
EMBEDDING_DIM=1536
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Instantiate:

```text
OpenAIEmbeddingProvider
DocumentRepository
DoclingDocumentParser
DocumentChunker
MilvusVectorStore
RAGService
```

- [ ] **Step 5: Update routes**

Keep existing route names where possible:

```text
POST /documents/upload
POST /documents/parse
GET /documents
GET /documents/content
GET /documents/file
POST /chat/stream
```

Change upload behavior so successful upload saves file, creates a `document` row, parses/indexes synchronously for this version, and returns `doc_id`.

- [ ] **Step 6: Run backend tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/main.py backend/app/schemas.py backend/tests/test_api_knowledge_base.py
git commit -m "feat: expose knowledge base document APIs"
```

## Task 9: Frontend Left Navigation And Knowledge Base Tab

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Update frontend state types**

In `frontend/app/page.tsx`, replace the active tab type with:

```ts
type ActiveView = "chat" | "knowledge";
```

Update document item type:

```ts
type DatasetItem = {
  id: string;
  name: string;
  file_type: string;
  storage_path: string;
  parse_status: "pending" | "parsing" | "parsed" | "failed";
  created_at: string;
  updated_at: string;
  chunks: number;
  metadata_json: Record<string, unknown>;
};
```

- [ ] **Step 2: Add upload state and handler**

Add state:

```ts
const [uploading, setUploading] = useState(false);
const [uploadError, setUploadError] = useState("");
```

Add handler:

```ts
async function handleUpload(file: File | null) {
  if (!file) return;
  setUploading(true);
  setUploadError("");
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`${API_BASE}/documents/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `请求失败: ${res.status}`);
    await loadDataset();
  } catch (err) {
    setUploadError(err instanceof Error ? err.message : "unknown error");
  } finally {
    setUploading(false);
  }
}
```

- [ ] **Step 3: Convert layout to left/right frame**

Render:

```tsx
<main className="app-frame">
  <aside className="sidebar">
    <div className="brand">知档 AI</div>
    <button className={activeView === "chat" ? "active" : ""}>模型对话</button>
    <button className={activeView === "knowledge" ? "active" : ""}>知识库</button>
    <button type="button" onClick={handleNewChat}>新对话</button>
  </aside>
  <section className="workspace">
    {activeView === "chat" ? chat view : knowledge view}
  </section>
</main>
```

- [ ] **Step 4: Build knowledge-base view**

The knowledge view includes:

```text
Top toolbar: upload button, refresh button
Status line: upload errors or loading state
Table columns: 文件名, 类型, 解析状态, 分块数, 更新时间, 操作
Actions: 查看
```

Accepted upload extensions:

```text
.pdf,.docx,.html,.htm,.xlsx,.xlsm,.xls,.md,.markdown
```

- [ ] **Step 5: Update CSS**

Add stable frame styles:

```css
.app-frame {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.sidebar {
  border-right: 1px solid var(--line);
  background: #f8fafc;
  padding: 16px;
}

.workspace {
  min-width: 0;
  background: var(--bg);
}
```

Keep the current chat visual language, but remove the top sticky nav once the sidebar owns navigation.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/app/page.tsx frontend/app/globals.css
git commit -m "feat: add knowledge base workspace"
```

## Task 10: End-To-End Verification And Docs

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/design-docs/backend-rag-pipeline.md`
- Modify: `docs/design-docs/frontend-chat-ui.md`
- Modify: `README.md`

- [ ] **Step 1: Update backend design docs**

Document:

```text
Docling parser -> ParsedDocument -> DocumentChunker -> SQLite document/document_chunk -> Milvus child/table vectors -> parent recall
```

Explicitly state that Chroma and `parent_store.json` are no longer source of truth.

- [ ] **Step 2: Update frontend design docs**

Document:

```text
Left sidebar
Chat workspace
Knowledge-base workspace
Upload and parse-status lifecycle
Document preview behavior
```

- [ ] **Step 3: Update development docs**

Add local requirements:

```text
Milvus running at MILVUS_URI
Docling installed in backend venv
METADATA_DB_PATH
EMBEDDING_DIM
```

Add smoke commands:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
uvicorn app.main:app --reload --port 8000

cd frontend
npm run build
npm run dev
```

- [ ] **Step 4: Manual smoke test**

Run backend and frontend, then verify:

```text
GET /health returns {"ok": true}
Knowledge-base upload accepts PDF/DOCX/HTML/Excel/Markdown
Uploaded document appears with parse_status="parsed"
Document row has chunk count > 0
Milvus count increases for child/table chunks only
Chat question streams answer
Sources include document name, title_path, and page range when available
Document preview opens
Feedback submission still creates retrievable knowledge
```

- [ ] **Step 5: Remove Chroma dependency after smoke passes**

Delete from `backend/requirements.txt`:

```text
chromadb==0.5.23
```

Do not delete `backend/chroma_db/` in this task. Leave old persisted files untouched unless the user explicitly asks for cleanup.

- [ ] **Step 6: Commit**

```powershell
git add README.md docs/ARCHITECTURE.md docs/DEVELOPMENT.md docs/design-docs/backend-rag-pipeline.md docs/design-docs/frontend-chat-ui.md backend/requirements.txt
git commit -m "docs: document milvus docling rag pipeline"
```

## Self-Review Checklist

- Spec coverage: Milvus migration, Docling parser, `DocumentParser`, `ParsedDocument`, structured elements, parent-child chunking, table chunk preservation, `EmbeddingProvider`, left/right UI, knowledge-base upload, and requested storage fields are covered.
- Placeholder scan: This plan intentionally avoids placeholder labels and specifies concrete paths, interfaces, tests, commands, and expected outcomes.
- Type consistency: `ParsedDocument`, `ParsedElement`, `Chunk`, `DocumentParser`, `DocumentChunker`, `EmbeddingProvider`, `OpenAIEmbeddingProvider`, `DocumentRepository`, and `MilvusVectorStore` names are consistent across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-10-milvus-docling-knowledge-base.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task and review between tasks for faster, cleaner iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans with checkpoints.
