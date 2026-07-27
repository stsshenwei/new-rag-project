from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.models.document_models import Chunk, ParsedImage
from app.models.processing_config import PROCESSING_VERSION


@dataclass(frozen=True)
class MultimodalResult:
    text: str
    provider: str
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


class OCRProvider(Protocol):
    name: str
    @property
    def available(self) -> bool: ...
    def extract_text(self, image: bytes, mime_type: str) -> MultimodalResult: ...


class CaptionProvider(Protocol):
    name: str
    @property
    def available(self) -> bool: ...
    def describe(self, image: bytes, mime_type: str) -> MultimodalResult: ...


class DisabledOCRProvider:
    name = "disabled"
    available = False

    def extract_text(self, image: bytes, mime_type: str) -> MultimodalResult:
        raise RuntimeError("OCR capability is disabled")


class DisabledCaptionProvider:
    name = "disabled"
    available = False

    def describe(self, image: bytes, mime_type: str) -> MultimodalResult:
        raise RuntimeError("Caption capability is disabled")


def image_result_chunk(
    *, doc_id: str, image: ParsedImage, result: MultimodalResult, result_type: str,
    parent_id: str | None, title_path: str = "", scope_metadata: dict | None = None,
) -> Chunk:
    if result_type not in {"image_ocr", "image_caption"}:
        raise ValueError("Unsupported multimodal chunk type")
    content = result.text.strip()
    return Chunk(
        id=f"{doc_id}::{image.image_id}::{result_type}", doc_id=doc_id, parent_id=parent_id,
        chunk_type=result_type, title_path=title_path, content=content, content_markdown=content,
        page_start=image.page_number, page_end=image.page_number, token_count=max(1, len(content) // 4),
        metadata={
            **(scope_metadata or {}), "image_id": image.image_id, "storage_key": image.storage_key,
            "source_type": image.source_type, "provider": result.provider, "confidence": result.confidence,
            "generated_evidence": True, "strategy": result_type, "processing_version": PROCESSING_VERSION,
            "size_unit": "chars", **result.metadata,
        },
    )
