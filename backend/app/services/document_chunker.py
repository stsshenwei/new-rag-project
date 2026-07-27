from app.models.document_models import Chunk, ParsedDocument, ParsedElement
from app.models.processing_config import PROCESSING_VERSION
from app.services.adaptive_chunker import AdaptiveChunkConfig, split_text, split_with_diagnostics


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class DocumentChunker:
    def __init__(
        self,
        parent_max_tokens: int = 2400,
        child_max_tokens: int = 600,
        child_overlap_tokens: int = 80,
        ocr_min_confidence: float = 0.0,
        strategy: str = "auto",
        parent_chunk_size_chars: int | None = None,
        child_chunk_size_chars: int | None = None,
        child_overlap_chars: int | None = None,
    ):
        # Legacy constructor names are retained as call-site compatibility only;
        # values are now explicit character targets and no longer multiplied by 4.
        self.parent_max_tokens = parent_chunk_size_chars or parent_max_tokens
        self.child_max_tokens = child_chunk_size_chars or child_max_tokens
        self.child_overlap_tokens = child_overlap_chars if child_overlap_chars is not None else child_overlap_tokens
        self.ocr_min_confidence = ocr_min_confidence
        self.strategy = strategy

    def chunk(self, parsed: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        text_elements = [element for element in parsed.elements if element.type not in {"table", "image"}]
        markdown = "\n\n".join(element.markdown for element in text_elements if element.markdown).strip()
        parent_cfg = AdaptiveChunkConfig(
            chunk_size_chars=self.parent_max_tokens,
            chunk_overlap_chars=min(self.child_overlap_tokens, self.parent_max_tokens // 2),
            strategy=self.strategy,
        )
        parent_parts, parent_diag = split_with_diagnostics(markdown, parent_cfg)
        for parent_index, parent_part in enumerate(parent_parts):
            parent_id = f"{parsed.doc_id}::parent-{parent_index}"
            title_path = self._title_path_for_offset(markdown, parent_part.start, parsed.elements)
            page_start, page_end = self._pages_for_title_path(title_path, parsed.elements)
            chunks.append(
                Chunk(
                    id=parent_id,
                    doc_id=parsed.doc_id,
                    parent_id=None,
                    chunk_type="parent",
                    title_path=title_path,
                    content=parent_part.content,
                    content_markdown=parent_part.content,
                    page_start=page_start,
                    page_end=page_end,
                    token_count=estimate_tokens(parent_part.content),
                    metadata={
                        "parent_index": parent_index,
                        "strategy": parent_part.strategy,
                        "processing_version": PROCESSING_VERSION,
                        "context_header": parent_part.context_header,
                        "size_unit": "chars",
                        "tier_chain": parent_diag.tier_chain,
                    },
                )
            )
            child_cfg = AdaptiveChunkConfig(
                chunk_size_chars=self.child_max_tokens,
                chunk_overlap_chars=self.child_overlap_tokens,
                strategy=self.strategy,
            )
            child_parts = [child for child in split_text(parent_part.content, child_cfg) if child.content.strip()]
            collapse_identical_child = (
                len(child_parts) == 1
                and self._normalized_content(child_parts[0].content) == self._normalized_content(parent_part.content)
            )
            for child_index, child in enumerate(child_parts):
                context_header = self._merge_context_headers(parent_part.context_header, child.context_header)
                chunks.append(
                    Chunk(
                        id=f"{parent_id}::child-{child_index}",
                        doc_id=parsed.doc_id,
                        parent_id=parent_id,
                        chunk_type="child",
                        title_path=title_path,
                        content=child.content,
                        content_markdown=child.content,
                        page_start=page_start,
                        page_end=page_end,
                        token_count=estimate_tokens(child.content),
                        metadata={
                            "child_index": child_index,
                            "strategy": child.strategy,
                            "processing_version": PROCESSING_VERSION,
                            "context_header": context_header,
                            "size_unit": "chars",
                            "source_start": parent_part.start + child.start,
                            "source_end": parent_part.start + child.end,
                            "collapsed_identical_parent": collapse_identical_child,
                            "collapse_parent_id": parent_id if collapse_identical_child else "",
                        },
                    )
                )

        for element in parsed.elements:
            if element.type == "table":
                chunks.append(self._table_chunk(parsed.doc_id, chunks, element.title_path, element, parsed.elements, element.page_start, element.page_end))
            elif element.type == "image" and self._ocr_text(element) and self._ocr_confidence(element) >= self.ocr_min_confidence:
                chunks.append(self._ocr_chunk(parsed.doc_id, chunks, element.title_path, element, element.page_start, element.page_end))
        return chunks

    def _title_path_for_offset(self, markdown: str, offset: int, elements: list[ParsedElement]) -> str:
        prefix = markdown[:offset]
        title_path = ""
        cursor = 0
        for element in elements:
            if element.type in {"table", "image"}:
                continue
            cursor += len(element.markdown) + 2
            if cursor > len(prefix):
                break
            if element.title_path:
                title_path = element.title_path
        if not title_path:
            title_path = next((element.title_path for element in elements if element.title_path), "")
        return title_path

    def _pages_for_title_path(self, title_path: str, elements: list[ParsedElement]):
        matching = [element for element in elements if element.title_path == title_path and element.page_start is not None]
        if not matching:
            matching = [element for element in elements if element.page_start is not None]
        return (
            min((element.page_start for element in matching), default=None),
            max((element.page_end for element in matching if element.page_end is not None), default=None),
        )

    def _merge_context_headers(self, parent: str, child: str) -> str:
        if not parent:
            return child
        if not child:
            return parent
        parent_lines = parent.splitlines()
        child_lines = child.splitlines()
        if parent_lines and child_lines and parent_lines[-1].strip() == child_lines[0].strip():
            child_lines = child_lines[1:]
        return "\n".join(parent_lines + child_lines)

    def _normalized_content(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines())

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
        parent_elements = [element for element in elements if element.type not in {"table", "image"}]
        content = "\n".join(element.text for element in parent_elements if element.text).strip()
        markdown = "\n\n".join(element.markdown for element in parent_elements if element.markdown).strip()
        title_path = next((element.title_path for element in elements if element.title_path), "")
        page_start = min((element.page_start for element in elements if element.page_start is not None), default=None)
        page_end = max((element.page_end for element in elements if element.page_end is not None), default=None)

        parent_parts = self._split_text_by_token_limit(content, self.parent_max_tokens) or [content]
        for parent_part_index, parent_text in enumerate(part for part in parent_parts if part.strip()):
            parent_id = f"{doc_id}::parent-{section_index}-{parent_part_index}"
            chunks.append(
                Chunk(
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
            )
            chunks.extend(self._child_chunks_for_parent(doc_id, parent_id, title_path, parent_text, page_start, page_end))

        for element in elements:
            if element.type == "table":
                chunks.append(self._table_chunk(doc_id, chunks, title_path, element, elements, page_start, page_end))
            elif element.type == "image" and self._ocr_text(element) and self._ocr_confidence(element) >= self.ocr_min_confidence:
                chunks.append(self._ocr_chunk(doc_id, chunks, title_path, element, page_start, page_end))
        return chunks

    def _child_chunks_for_parent(self, doc_id: str, parent_id: str, title_path: str, text: str, page_start, page_end) -> list[Chunk]:
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
            for idx, part in enumerate(self._split_text_by_token_limit(text, self.child_max_tokens, self.child_overlap_tokens))
            if part.strip()
        ]

    def _table_chunk(
        self,
        doc_id: str,
        existing_chunks: list[Chunk],
        title_path: str,
        element: ParsedElement,
        section_elements: list[ParsedElement],
        page_start,
        page_end,
    ) -> Chunk:
        parent_id = self._parent_id_for_element(doc_id, existing_chunks, title_path, element, "table")
        fields = self._table_fields(element)
        rows = element.metadata.get("rows", [])
        caption = str(element.metadata.get("caption", "")).strip()
        nearby_text = self._nearby_table_text(section_elements, element.element_id)
        summary = self._summarize_table(caption, nearby_text, fields, element.text)
        llm_context = "\n\n".join(part for part in [caption, nearby_text, element.markdown, element.html] if part)
        return Chunk(
            id=f"{parent_id}::table-{len([chunk for chunk in existing_chunks if chunk.chunk_type == 'table'])}",
            doc_id=doc_id,
            parent_id=parent_id,
            chunk_type="table",
            title_path=element.title_path or title_path,
            content=element.text,
            content_markdown=element.markdown,
            page_start=element.page_start if element.page_start is not None else page_start,
            page_end=element.page_end if element.page_end is not None else page_end,
            token_count=estimate_tokens(element.text),
            metadata={
                "caption": caption,
                "fields": fields,
                "rows": rows if isinstance(rows, list) else [],
                "row_count": int(element.metadata.get("row_count", len(rows) if isinstance(rows, list) else 0) or 0),
                "column_count": int(element.metadata.get("column_count", len(fields)) or 0),
                "nearby_text": nearby_text,
                "summary": summary,
                "llm_context": llm_context,
                "html": element.html,
                "strategy": "table",
                "processing_version": PROCESSING_VERSION,
                "size_unit": "chars",
            },
        )

    def _table_fields(self, element: ParsedElement) -> list[str]:
        if "fields" in element.metadata and isinstance(element.metadata["fields"], list):
            return [str(field) for field in element.metadata["fields"]]
        first_line = next((line for line in element.markdown.splitlines() if line.strip().startswith("|")), "")
        return [cell.strip() for cell in first_line.strip("|").split("|") if cell.strip()]

    def _ocr_chunk(self, doc_id: str, existing_chunks: list[Chunk], title_path: str, element: ParsedElement, page_start, page_end) -> Chunk:
        parent_id = self._parent_id_for_element(doc_id, existing_chunks, title_path, element, "ocr")
        text = self._ocr_text(element)
        confidence = self._ocr_confidence(element)
        return Chunk(
            id=f"{parent_id}::ocr-{len([chunk for chunk in existing_chunks if chunk.chunk_type == 'ocr'])}",
            doc_id=doc_id,
            parent_id=parent_id,
            chunk_type="ocr",
            title_path=element.title_path or title_path,
            content=text,
            content_markdown=element.markdown or text,
            page_start=element.page_start if element.page_start is not None else page_start,
            page_end=element.page_end if element.page_end is not None else page_end,
            token_count=estimate_tokens(text),
            metadata={
                "source": element.metadata.get("source", "docling_ocr"),
                "provider": element.metadata.get("provider", "docling"),
                "confidence": confidence,
                "caption": element.metadata.get("caption", ""),
                "figure_refs": element.metadata.get("figure_refs", []),
                "parse_source": element.metadata.get("parse_source", "docling_ocr"),
                "strategy": "ocr",
                "processing_version": PROCESSING_VERSION,
                "size_unit": "chars",
                "image_id": element.metadata.get("image_id", ""),
                "storage_key": element.metadata.get("storage_key", ""),
                "source_type": element.metadata.get("source_type", element.metadata.get("parse_source", "docling_ocr")),
            },
        )

    def _parent_id_for_element(
        self,
        doc_id: str,
        existing_chunks: list[Chunk],
        title_path: str,
        element: ParsedElement,
        fallback_kind: str,
    ) -> str:
        parents = [chunk for chunk in existing_chunks if chunk.chunk_type == "parent"]
        if not parents:
            return f"{doc_id}::parent-{fallback_kind}"
        desired_title = element.title_path or title_path
        candidates = [parent for parent in parents if self._title_paths_match(parent.title_path, desired_title)]
        if not candidates:
            return parents[-1].id
        page_start = element.page_start
        page_end = element.page_end if element.page_end is not None else page_start
        page_matches = [
            parent for parent in candidates
            if self._pages_overlap(parent.page_start, parent.page_end, page_start, page_end)
        ]
        return (page_matches or candidates)[0].id

    def _title_paths_match(self, parent_title: str, element_title: str) -> bool:
        parent_title = parent_title.strip()
        element_title = element_title.strip()
        if not parent_title or not element_title:
            return False
        return (
            parent_title == element_title
            or parent_title.startswith(f"{element_title} /")
            or element_title.startswith(f"{parent_title} /")
        )

    def _pages_overlap(self, parent_start, parent_end, element_start, element_end) -> bool:
        if parent_start is None or element_start is None:
            return False
        parent_end = parent_end if parent_end is not None else parent_start
        element_end = element_end if element_end is not None else element_start
        return int(parent_start) <= int(element_end) and int(element_start) <= int(parent_end)

    def _ocr_text(self, element: ParsedElement) -> str:
        return str(element.metadata.get("ocr_text") or element.text or "").strip()

    def _ocr_confidence(self, element: ParsedElement) -> float:
        return float(element.metadata.get("confidence", element.metadata.get("ocr_confidence", 1.0)) or 0.0)

    def _nearby_table_text(self, section_elements: list[ParsedElement], table_element_id: str) -> str:
        index = next((idx for idx, item in enumerate(section_elements) if item.element_id == table_element_id), -1)
        if index < 0:
            return ""
        nearby = []
        for idx in [index - 1, index + 1]:
            if 0 <= idx < len(section_elements) and section_elements[idx].type in {"paragraph", "list"}:
                nearby.append(section_elements[idx].text)
        return "\n".join(text for text in nearby if text)

    def _summarize_table(self, caption: str, nearby_text: str, fields: list[str], table_text: str) -> str:
        field_text = "、".join(field for field in fields if field)
        sample = " ".join(table_text.split())[:300]
        return "。".join(part for part in [caption, nearby_text, f"字段包括 {field_text}" if field_text else "", sample] if part)

    def _split_text_by_token_limit(self, text: str, max_tokens: int, overlap_tokens: int = 0) -> list[str]:
        if not text:
            return []
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
