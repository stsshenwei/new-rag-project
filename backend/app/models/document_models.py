from dataclasses import dataclass, field
from typing import Any, Literal

from app.models.processing_config import PROCESSING_VERSION

ElementType = Literal["title", "paragraph", "table", "image", "list", "code", "unknown"]
ChunkType = Literal["parent", "child", "table", "ocr", "image_ocr", "image_caption", "summary"]


@dataclass(frozen=True)
class ParsedImage:
    image_id: str
    storage_key: str
    source_type: str
    page_number: int | None = None
    mime_type: str = "image/jpeg"
    width: int | None = None
    height: int | None = None
    caption: str = ""
    parent_element_id: str | None = None
    data: bytes = field(default=b"", repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseDiagnostics:
    requested_engine: str = "builtin"
    effective_engine: str = "builtin"
    parser_name: str = ""
    fallback_reason: str = ""
    parse_duration_ms: int = 0
    warnings: tuple[str, ...] = ()


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
    markdown: str = ""
    images: list[ParsedImage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: ParseDiagnostics = field(default_factory=ParseDiagnostics)


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
    def strategy(self) -> str:
        value = str(self.metadata.get("strategy") or "").strip()
        if value:
            return value
        if self.chunk_type in {"image_ocr", "image_caption", "ocr", "table"}:
            return self.chunk_type
        return "legacy"

    @property
    def processing_version(self) -> str:
        return str(self.metadata.get("processing_version") or PROCESSING_VERSION)

    @property
    def size_unit(self) -> str:
        return str(self.metadata.get("size_unit") or "chars")

    @property
    def image_id(self) -> str:
        return str(self.metadata.get("image_id") or "")

    @property
    def storage_key(self) -> str:
        return str(self.metadata.get("storage_key") or "")

    @property
    def image_provenance(self) -> dict[str, Any]:
        return {
            key: self.metadata.get(key)
            for key in ("image_id", "storage_key", "source_type", "provider", "confidence")
            if self.metadata.get(key) not in (None, "")
        }

    @property
    def embedding_text(self) -> str:
        context_header = str(self.metadata.get("context_header", "")).strip()
        caption = str(self.metadata.get("caption", "")).strip()
        summary = str(self.metadata.get("summary", "")).strip()
        nearby_text = str(self.metadata.get("nearby_text", "")).strip()
        fields = self.metadata.get("fields", [])
        table_markdown = self.content_markdown.strip() if self.chunk_type == "table" else ""

        pieces = [context_header, self.title_path.strip(), self.content.strip()]
        if caption:
            pieces.append(caption)
        if nearby_text:
            pieces.append(nearby_text)
        if summary:
            pieces.append(summary)
        if fields:
            pieces.append("字段: " + ", ".join(str(field) for field in fields))
        if table_markdown and table_markdown != self.content.strip():
            pieces.append(table_markdown)
        return "\n".join(piece for piece in pieces if piece)

    @property
    def llm_context(self) -> str:
        context = str(self.metadata.get("llm_context", "")).strip()
        if context:
            return context
        return self.content_markdown or self.content
