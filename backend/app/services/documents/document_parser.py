import hashlib
import html
import io
import mimetypes
import re
import threading
import time
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from app.models.document_models import ParseDiagnostics, ParsedDocument, ParsedElement, ParsedImage
from app.models.processing_config import ParserErrorCode
from app.services.documents.document_loader import load_docx, load_excel, load_text, read_text_with_fallback

SUPPORTED_PARSE_EXTS = {
    ".pdf",
    ".docx",
    ".html",
    ".htm",
    ".xlsx",
    ".xlsm",
    ".xls",
    ".md",
    ".markdown",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
}
PDFIUM_LOCK = threading.RLock()


class ParserError(RuntimeError):
    code = ParserErrorCode.PARSER_FAILED.value

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code or self.code


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        raise NotImplementedError


class DoclingDocumentParser(DocumentParser):
    def parse(self, file_path: Path, requested_engine: str = "docling") -> ParsedDocument:
        started = time.perf_counter()
        markdown, exported_html = self._parse_with_docling(file_path)
        if not markdown.strip() and not exported_html.strip():
            raise ParserError("Docling produced no parseable content", ParserErrorCode.PARSER_ENGINE_FAILED.value)
        elements = elements_from_markdown_and_html(markdown, exported_html, parse_source="docling")
        return ParsedDocument(
            doc_id=stable_doc_id(file_path),
            file_name=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            elements=elements,
            markdown=markdown,
            diagnostics=ParseDiagnostics(requested_engine, "docling", self.__class__.__name__, parse_duration_ms=int((time.perf_counter() - started) * 1000)),
        )

    def _parse_with_docling(self, file_path: Path) -> tuple[str, str]:
        try:
            from docling.document_converter import DocumentConverter
        except Exception as exc:
            raise ParserError("Docling is unavailable", ParserErrorCode.PARSER_ENGINE_UNAVAILABLE.value) from exc

        try:
            result = DocumentConverter().convert(file_path)
            document = result.document
            markdown = document.export_to_markdown() if hasattr(document, "export_to_markdown") else ""
            exported_html = document.export_to_html() if hasattr(document, "export_to_html") else ""
            return markdown or "", exported_html or ""
        except Exception as exc:
            raise ParserError("Docling failed to parse the document", ParserErrorCode.PARSER_ENGINE_FAILED.value) from exc

    def extract_ocr_elements(self, file_path: Path) -> list[ParsedElement]:
        return []


class BuiltinMarkdownParser(DocumentParser):
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        started = time.perf_counter()
        encoding = ""
        if file_path.suffix.lower() in {".txt", ".md", ".markdown"}:
            markdown, encoding = read_text_with_fallback(file_path)
        else:
            markdown = load_text(file_path)
        warnings = (f"text_encoding:{encoding}",) if encoding and encoding not in {"utf-8", "utf-8-sig"} else ()
        return ParsedDocument(
            doc_id=stable_doc_id(file_path),
            file_name=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            elements=elements_from_markdown_and_html(markdown, "", parse_source="builtin_markdown"),
            markdown=markdown,
            diagnostics=ParseDiagnostics(
                requested_engine,
                "builtin",
                self.__class__.__name__,
                parse_duration_ms=int((time.perf_counter() - started) * 1000),
                warnings=warnings,
            ),
        )


class MarkdownFallbackParser(BuiltinMarkdownParser):
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        parsed = super().parse(file_path, requested_engine=requested_engine)
        return ParsedDocument(
            parsed.doc_id,
            parsed.file_name,
            parsed.file_type,
            elements_from_markdown_and_html(parsed.markdown, "", parse_source="fallback"),
            parsed.markdown,
            parsed.images,
            parsed.metadata,
            ParseDiagnostics(
                requested_engine,
                "builtin",
                self.__class__.__name__,
                parse_duration_ms=parsed.diagnostics.parse_duration_ms,
                warnings=parsed.diagnostics.warnings,
            ),
        )


class BuiltinDocxParser(DocumentParser):
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        started = time.perf_counter()
        markdown = load_docx(file_path)
        return ParsedDocument(
            doc_id=stable_doc_id(file_path),
            file_name=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            elements=elements_from_markdown_and_html(markdown, "", parse_source="builtin_docx"),
            markdown=markdown,
            diagnostics=ParseDiagnostics(requested_engine, "builtin", self.__class__.__name__, parse_duration_ms=int((time.perf_counter() - started) * 1000)),
        )


class BuiltinExcelParser(DocumentParser):
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        started = time.perf_counter()
        markdown = load_excel(file_path)
        return ParsedDocument(
            doc_id=stable_doc_id(file_path),
            file_name=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            elements=elements_from_markdown_and_html(markdown, "", parse_source="builtin_excel"),
            markdown=markdown,
            diagnostics=ParseDiagnostics(requested_engine, "builtin", self.__class__.__name__, parse_duration_ms=int((time.perf_counter() - started) * 1000)),
        )


class BuiltinPDFParser(DocumentParser):
    def __init__(
        self,
        force_scanned: bool = False,
        render_dpi: int = 200,
        jpeg_quality: int = 90,
        max_pages: int = 1000,
        max_image_edge_px: int = 2400,
        render_concurrency: int = 2,
        render_all_fallback: bool = True,
    ):
        self.force_scanned = force_scanned
        self.render_dpi = max(72, min(render_dpi, 600))
        self.jpeg_quality = max(1, min(jpeg_quality, 95))
        self.max_pages = max_pages
        self.max_image_edge_px = max(256, int(max_image_edge_px))
        self.render_concurrency = max(1, int(render_concurrency))
        self.render_all_fallback = render_all_fallback
        self._render_semaphore = threading.BoundedSemaphore(self.render_concurrency)

    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        started = time.perf_counter()
        try:
            import pypdfium2 as pdfium
        except Exception as exc:
            raise ParserError("pypdfium2 is unavailable", ParserErrorCode.PARSER_ENGINE_UNAVAILABLE.value) from exc
        content = file_path.read_bytes()
        warnings: list[str] = []
        fallback_reason = ""
        try:
            parsed = self._parse_pdf_content(pdfium, content, file_path, warnings, render_all=False)
        except ParserError:
            raise
        except Exception as exc:
            if not self.render_all_fallback:
                raise ParserError("PDF page routing failed", ParserErrorCode.PARSER_FAILED.value) from exc
            warnings.append(f"pdf_render_all_fallback:{exc.__class__.__name__}")
            fallback_reason = "render_all_after_routing_failure"
            parsed = self._parse_pdf_content(pdfium, content, file_path, warnings, render_all=True)

        markdown = parsed["markdown"]
        metadata = parsed["metadata"]
        metadata.update({
            "pdf_render_dpi": self.render_dpi,
            "pdf_jpeg_quality": self.jpeg_quality,
            "pdf_max_image_edge_px": self.max_image_edge_px,
            "pdf_render_concurrency": self.render_concurrency,
        })
        return ParsedDocument(
            doc_id=stable_doc_id(file_path), file_name=file_path.name, file_type="pdf",
            elements=elements_from_markdown_and_html(markdown, "", parse_source="builtin_pdf"), markdown=markdown,
            images=parsed["images"], metadata=metadata,
            diagnostics=ParseDiagnostics(
                requested_engine, "builtin", self.__class__.__name__, fallback_reason,
                parse_duration_ms=int((time.perf_counter() - started) * 1000),
                warnings=tuple(warnings),
            ),
        )

    def _parse_pdf_content(self, pdfium, content: bytes, file_path: Path, warnings: list[str], render_all: bool) -> dict:
        images: list[ParsedImage] = []
        page_texts: list[str] = []
        page_classes: list[str] = []
        page_image_refs: dict[int, list[str]] = {}
        text_pages = scanned_pages = 0
        embedded_count = vector_count = 0
        page_count = 0
        with PDFIUM_LOCK:
            try:
                pdf = pdfium.PdfDocument(content)
            except Exception as exc:
                message = str(exc).lower()
                code = ParserErrorCode.PDF_PASSWORD_REQUIRED.value if "password" in message else ParserErrorCode.PDF_OPEN_FAILED.value
                raise ParserError("Unable to open PDF", code) from exc
            try:
                page_count = len(pdf)
                if page_count > self.max_pages:
                    raise ParserError("PDF page limit exceeded", ParserErrorCode.PDF_PAGE_LIMIT_EXCEEDED.value)
                for page_index in range(page_count):
                    page = pdf[page_index]
                    try:
                        text_page = page.get_textpage()
                        try:
                            plain = text_page.get_text_range() or ""
                            layout = _layout_ordered_pdf_text(text_page)
                        finally:
                            close = getattr(text_page, "close", None)
                            if callable(close): close()
                        image_ratio = _pdf_page_image_area_ratio(page)
                        scanned = render_all or self.force_scanned or image_ratio >= 0.50 or (len(plain.strip()) < 20 and image_ratio >= 0.10)
                        if scanned:
                            scanned_pages += 1
                            data, width, height = self._render_page_jpeg(page)
                            key = f"images/{file_path.stem}_page_{page_index + 1}.jpg"
                            images.append(ParsedImage(
                                f"page-{page_index + 1}", key, "scanned_pdf", page_index + 1,
                                width=width, height=height, data=data,
                                metadata={"page_position": "full_page", "render_dpi": self.render_dpi},
                            ))
                            page_texts.append("")
                            page_classes.append("scanned")
                            page_image_refs[page_index] = [f"![{file_path.stem}_page_{page_index + 1}.jpg]({key})"]
                        else:
                            text_pages += 1
                            native_text, used_layout = _select_native_pdf_text(plain, layout)
                            if used_layout:
                                warnings.append(f"page_{page_index + 1}:layout_text_fallback")
                            page_texts.append(_postprocess_native_pdf_text(native_text))
                            page_classes.append("text")
                            refs = []
                            for image_index, obj in enumerate(_eligible_pdf_images(page, min_area_ratio=0.02), start=1):
                                try:
                                    left, bottom, right, top = obj.get_bounds()
                                    pil_image = _bound_image(obj.get_bitmap().to_pil().convert("RGB"), self.max_image_edge_px)
                                    buffer = io.BytesIO()
                                    pil_image.save(buffer, format="JPEG", quality=self.jpeg_quality)
                                    key = f"images/{file_path.stem}_p{page_index + 1}_img{image_index}.jpg"
                                    image_id = f"page-{page_index + 1}-image-{image_index}"
                                    images.append(ParsedImage(image_id, key, "embedded_image", page_index + 1,
                                                              width=pil_image.width, height=pil_image.height, data=buffer.getvalue(),
                                                              metadata={"bbox": [left, bottom, right, top], "page_position": _page_position(page, (left, bottom, right, top))}))
                                    refs.append(f"![{file_path.stem}_p{page_index + 1}_img{image_index}.jpg]({key})")
                                    embedded_count += 1
                                except Exception:
                                    continue
                            for figure_index, bounds in enumerate(_eligible_pdf_vector_bounds(page, min_area_ratio=0.02), start=1):
                                try:
                                    data, width, height = self._render_page_jpeg(page, bounds)
                                    key = f"images/{file_path.stem}_p{page_index + 1}_vector{figure_index}.jpg"
                                    image_id = f"page-{page_index + 1}-vector-{figure_index}"
                                    images.append(ParsedImage(image_id, key, "vector_figure", page_index + 1,
                                                              width=width, height=height, data=data,
                                                              metadata={"bbox": list(bounds), "page_position": _page_position(page, bounds)}))
                                    refs.append(f"![{file_path.stem}_p{page_index + 1}_vector{figure_index}.jpg]({key})")
                                    vector_count += 1
                                except Exception as exc:
                                    warnings.append(f"page_{page_index + 1}:vector_clip_failed:{exc.__class__.__name__}")
                            page_image_refs[page_index] = refs
                    finally:
                        close = getattr(page, "close", None)
                        if callable(close): close()
            finally:
                close = getattr(pdf, "close", None)
                if callable(close): close()
        page_texts = _strip_repeating_pdf_lines(page_texts, page_classes)
        page_blocks = []
        for page_index, page_class in enumerate(page_classes):
            parts = []
            if page_class == "text" and page_texts[page_index].strip():
                parts.append(page_texts[page_index].strip())
            parts.extend(page_image_refs.get(page_index, []))
            page_blocks.append("\n\n".join(parts))
        markdown = "\n\n\f\n\n".join(page_blocks).strip()
        source_classification = "hybrid" if text_pages and scanned_pages else "scanned" if scanned_pages else "native"
        return {
            "markdown": markdown,
            "images": images,
            "metadata": {
                "page_count": page_count,
                "text_page_count": text_pages,
                "scanned_page_count": scanned_pages,
                "embedded_image_count": embedded_count,
                "vector_figure_count": vector_count,
                "image_source_type": "scanned_pdf" if scanned_pages else "pdf_text_layer",
                "source_classification": source_classification,
                "render_all_fallback": render_all,
            },
        }

    def _render_page_jpeg(self, page, bounds: tuple[float, float, float, float] | None = None) -> tuple[bytes, int, int]:
        with self._render_semaphore:
            crop = (0, 0, 0, 0)
            if bounds is not None:
                width, height = page.get_size()
                left, bottom, right, top = bounds
                crop = (max(0.0, left), max(0.0, bottom), max(0.0, width - right), max(0.0, height - top))
            bitmap = page.render(scale=self.render_dpi / 72, crop=crop)
            try:
                pil_image = _bound_image(bitmap.to_pil().convert("RGB"), self.max_image_edge_px)
                buffer = io.BytesIO()
                pil_image.save(buffer, format="JPEG", quality=self.jpeg_quality)
                return buffer.getvalue(), pil_image.width, pil_image.height
            finally:
                close = getattr(bitmap, "close", None)
                if callable(close): close()


class BuiltinImageParser(DocumentParser):
    def parse(self, file_path: Path, requested_engine: str = "builtin") -> ParsedDocument:
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        key = f"images/{file_path.name}"
        markdown = f"![{file_path.stem}]({key})"
        return ParsedDocument(
            stable_doc_id(file_path), file_path.name, file_path.suffix.lower().lstrip("."),
            elements_from_markdown_and_html(markdown, "", "builtin_image"), markdown,
            [ParsedImage("image-1", key, "uploaded_image", 1, mime_type=mime, data=file_path.read_bytes())],
            {"page_count": 1, "image_source_type": "uploaded_image"},
            ParseDiagnostics(requested_engine, "builtin", self.__class__.__name__),
        )


class ParserEngineRegistry:
    def __init__(self):
        self._engines: dict[str, dict[str, type[DocumentParser]]] = {}
        self._availability: dict[str, callable] = {}

    def register(self, name: str, parsers: dict[str, type[DocumentParser]], availability=None) -> None:
        self._engines[name] = {ext.lower().lstrip("."): parser for ext, parser in parsers.items()}
        if availability: self._availability[name] = availability

    def is_available(self, name: str) -> tuple[bool, str]:
        probe = self._availability.get(name)
        if not probe: return name in self._engines, "" if name in self._engines else "engine is not registered"
        try: return (True, "") if probe() else (False, "engine dependency is unavailable")
        except Exception as exc: return False, str(exc)

    def resolve(self, engine: str, extension: str) -> tuple[type[DocumentParser], str, str]:
        requested = engine or "builtin"
        ext = extension.lower().lstrip(".")
        available, reason = self.is_available(requested)
        if available and ext in self._engines.get(requested, {}): return self._engines[requested][ext], requested, ""
        builtin = self._engines.get("builtin", {}).get(ext)
        if builtin: return builtin, "builtin", reason or f"{requested} does not support .{ext}"
        raise ParserError(f"Unsupported document type: .{ext}", ParserErrorCode.UNSUPPORTED_FORMAT.value)

    def parse(self, file_path: Path, engine: str = "builtin", **parser_options) -> ParsedDocument:
        parser_cls, effective, fallback = self.resolve(engine, file_path.suffix)
        parser = parser_cls(**parser_options) if parser_cls is BuiltinPDFParser else parser_cls()
        parsed = parser.parse(file_path, requested_engine=engine)
        if fallback:
            parsed = ParsedDocument(parsed.doc_id, parsed.file_name, parsed.file_type, parsed.elements, parsed.markdown, parsed.images,
                                    parsed.metadata, ParseDiagnostics(engine, effective, parser_cls.__name__, fallback,
                                                                    parsed.diagnostics.parse_duration_ms, parsed.diagnostics.warnings))
        return parsed

    def list_engines(self) -> list[dict]:
        result = []
        for name, parsers in self._engines.items():
            available, reason = self.is_available(name)
            result.append({"name": name, "file_types": sorted(parsers), "available": available, "unavailable_reason": reason})
        return result


def _docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except Exception:
        return False


PARSER_REGISTRY = ParserEngineRegistry()
PARSER_REGISTRY.register("builtin", {
    "pdf": BuiltinPDFParser, "docx": BuiltinDocxParser, "txt": BuiltinMarkdownParser, "md": BuiltinMarkdownParser, "markdown": BuiltinMarkdownParser,
    "html": MarkdownFallbackParser, "htm": MarkdownFallbackParser, "xlsx": BuiltinExcelParser, "xlsm": BuiltinExcelParser,
    "xls": BuiltinExcelParser, **{ext: BuiltinImageParser for ext in ("jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp")},
})
PARSER_REGISTRY.register("docling", {"pdf": DoclingDocumentParser, "docx": DoclingDocumentParser}, _docling_available)


class RegistryDocumentParser(DocumentParser):
    def __init__(self, engine: str = "builtin", **parser_options):
        self.engine = engine
        self.parser_options = parser_options

    def parse(self, file_path: Path, requested_engine: str | None = None) -> ParsedDocument:
        return PARSER_REGISTRY.parse(file_path, engine=requested_engine or self.engine, **self.parser_options)


def get_parser_for_path(file_path: Path, engine: str = "builtin") -> DocumentParser:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_PARSE_EXTS:
        raise ValueError(f"Unsupported document type: {suffix}")
    parser_cls, _, _ = PARSER_REGISTRY.resolve(engine, suffix)
    return parser_cls()


def parse_with_engine(file_path: Path, engine: str = "builtin", **parser_options) -> ParsedDocument:
    return PARSER_REGISTRY.parse(file_path, engine=engine, **parser_options)


def _postprocess_native_pdf_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines()]
    output = []
    for line in lines:
        if not line: continue
        if len(line) <= 100 and not re.search(r"[.!?。！？]$", line) and (line.isupper() or re.match(r"^(?:\d+(?:\.\d+)*|第.+[章节])\s+", line)):
            line = f"## {line}"
        output.append(line)
    return "\n".join(output)


def _postprocess_native_pdf_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines()]
    output = []
    for line in lines:
        if not line:
            continue
        if len(line) <= 100 and not re.search(r"[.!?\u3002\uff01\uff1f]$", line) and (
            line.isupper() or re.match(r"^(?:\d+(?:\.\d+)*|第.+[章节])\s+", line)
        ):
            line = f"## {line}"
        output.append(line)
    return "\n".join(output)


def _pdf_plain_text_quality(text: str) -> float:
    stripped = text.strip()
    if len(stripped) < 20:
        return 0.0
    chars = [char for char in stripped if not char.isspace()]
    if not chars:
        return 0.0
    printable_ratio = sum(1 for char in chars if char.isprintable()) / len(chars)
    alpha_ratio = sum(1 for char in chars if char.isalnum() or "\u4e00" <= char <= "\u9fff") / len(chars)
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    single_char_ratio = (sum(1 for line in lines if len(line) <= 1) / len(lines)) if lines else 0.0
    return max(0.0, min(1.0, printable_ratio * 0.45 + alpha_ratio * 0.45 + (1.0 - single_char_ratio) * 0.10))


def _layout_ordered_pdf_text(text_page) -> str:
    try:
        count = text_page.count_chars()
    except Exception:
        return ""
    chars = []
    for index in range(count):
        try:
            char = text_page.get_text_range(index, 1)
            if not char or char in "\r\n":
                continue
            left, bottom, right, top = text_page.get_charbox(index)
            if char.isspace() and left == right and bottom == top:
                continue
            chars.append({"char": char, "left": left, "right": right, "mid_y": (bottom + top) / 2, "width": max(0.1, right - left)})
        except Exception:
            continue
    if not chars:
        return ""
    tolerance = max(3.0, sum(item["width"] for item in chars) / max(1, len(chars)) * 0.8)
    lines: list[list[dict]] = []
    for item in sorted(chars, key=lambda value: (-value["mid_y"], value["left"])):
        for line in lines:
            if abs(line[0]["mid_y"] - item["mid_y"]) <= tolerance:
                line.append(item)
                break
        else:
            lines.append([item])
    output = []
    for line in lines:
        ordered = sorted(line, key=lambda value: value["left"])
        pieces = []
        previous_right = None
        average_width = max(1.0, sum(item["width"] for item in ordered) / max(1, len(ordered)))
        for item in ordered:
            if previous_right is not None and item["left"] - previous_right > average_width * 0.9:
                pieces.append(" ")
            pieces.append(item["char"])
            previous_right = max(previous_right or item["right"], item["right"])
        output.append("".join(pieces).strip())
    return "\n".join(line for line in output if line)


def _select_native_pdf_text(plain: str, layout: str) -> tuple[str, bool]:
    plain_quality = _pdf_plain_text_quality(plain)
    layout_quality = _pdf_plain_text_quality(layout)
    if layout and (plain_quality < 0.72 or (layout_quality > plain_quality + 0.08 and _normalized_words(layout) != _normalized_words(plain))):
        return layout, True
    return plain, False


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def _bound_image(image, max_edge: int):
    width, height = image.size
    edge = max(width, height)
    if edge <= max_edge:
        return image
    scale = max_edge / edge
    try:
        from PIL import Image
        resampling = Image.Resampling.LANCZOS
    except Exception:
        resampling = 1
    return image.resize((max(1, int(width * scale)), max(1, int(height * scale))), resampling)


def _pdf_page_image_area_ratio(page) -> float:
    try:
        import pypdfium2.raw as raw
        width, height = page.get_size()
        page_area = float(width) * float(height)
        if page_area <= 0: return 0.0
        area = 0.0
        for obj in page.get_objects():
            try:
                if obj.type == raw.FPDF_PAGEOBJ_IMAGE:
                    left, bottom, right, top = obj.get_bounds()
                    area += abs((right - left) * (top - bottom))
            except Exception:
                continue
        return area / page_area
    except Exception:
        return 0.0


def _eligible_pdf_images(page, min_area_ratio: float):
    try:
        import pypdfium2.raw as raw
        width, height = page.get_size()
        area = max(1.0, float(width) * float(height))
        result = []
        for obj in page.get_objects():
            try:
                if obj.type != raw.FPDF_PAGEOBJ_IMAGE: continue
                left, bottom, right, top = obj.get_bounds()
                if abs((right - left) * (top - bottom)) / area >= min_area_ratio:
                    result.append(obj)
            except Exception:
                continue
        return result
    except Exception:
        return []


def _eligible_pdf_vector_bounds(page, min_area_ratio: float) -> list[tuple[float, float, float, float]]:
    try:
        import pypdfium2.raw as raw
        width, height = page.get_size()
        area = max(1.0, float(width) * float(height))
        result = []
        for obj in page.get_objects():
            try:
                if obj.type not in {raw.FPDF_PAGEOBJ_PATH, raw.FPDF_PAGEOBJ_SHADING, raw.FPDF_PAGEOBJ_FORM}:
                    continue
                left, bottom, right, top = obj.get_bounds()
                obj_width = abs(right - left)
                obj_height = abs(top - bottom)
                if (obj_width * obj_height) / area >= min_area_ratio and obj_width >= 20 and obj_height >= 20:
                    result.append((left, bottom, right, top))
            except Exception:
                continue
        return result
    except Exception:
        return []


def _page_position(page, bounds: tuple[float, float, float, float]) -> str:
    try:
        width, height = page.get_size()
        left, bottom, right, top = bounds
        mid_x = (left + right) / 2
        mid_y = (bottom + top) / 2
        vertical = "top" if mid_y >= height * 0.66 else "bottom" if mid_y <= height * 0.33 else "middle"
        horizontal = "left" if mid_x <= width * 0.33 else "right" if mid_x >= width * 0.66 else "center"
        return f"{vertical}_{horizontal}"
    except Exception:
        return "unknown"


def _strip_repeating_pdf_lines(texts: list[str], classes: list[str]) -> list[str]:
    from collections import Counter
    indices = [index for index, value in enumerate(classes) if value == "text"]
    if len(indices) < 4: return texts
    counts = Counter()
    for index in indices:
        lines = [line.strip() for line in texts[index].splitlines() if line.strip()]
        if lines:
            for value in {lines[0], lines[-1]}:
                if len(value) <= 80: counts[value] += 1
    threshold = max(2, int(len(indices) * 0.6))
    repeated = {value for value, count in counts.items() if count >= threshold}
    return ["\n".join(line for line in text.splitlines() if line.strip() not in repeated) if classes[index] == "text" else text
            for index, text in enumerate(texts)]


def stable_doc_id(file_path: Path) -> str:
    try:
        stat = file_path.stat()
        raw = f"{file_path.resolve()}::{stat.st_size}::{stat.st_mtime_ns}"
    except OSError:
        raw = str(file_path.resolve())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def elements_from_markdown_and_html(markdown: str, exported_html: str, parse_source: str = "fallback") -> list[ParsedElement]:
    html_blocks = _html_blocks(exported_html)
    elements: list[ParsedElement] = []
    title_stack: list[str] = []
    pending_table: list[str] = []
    html_index = 0

    def flush_table() -> None:
        nonlocal html_index
        if not pending_table:
            return
        markdown_table = "\n".join(pending_table)
        fields = [cell.strip() for cell in pending_table[0].strip("|").split("|") if cell.strip()]
        rows = _table_rows(markdown_table)
        caption = elements[-1].text if elements and _looks_like_caption(elements[-1].text) else ""
        elements.append(
            ParsedElement(
                element_id=f"el-{uuid4().hex}",
                type="table",
                text=_table_text(markdown_table),
                markdown=markdown_table,
                html=html_blocks[html_index] if html_index < len(html_blocks) else "",
                page_start=None,
                page_end=None,
                level=None,
                title_path="/".join(title_stack),
                metadata={
                    "fields": fields,
                    "rows": rows,
                    "row_count": len(rows),
                    "column_count": len(fields),
                    "caption": caption,
                    "parse_source": parse_source,
                    "layout": {},
                    "figure_refs": [],
                },
            )
        )
        html_index += 1
        pending_table.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush_table()
            continue
        if line.startswith("|") and line.endswith("|"):
            pending_table.append(line)
            continue
        flush_table()

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        element_type = "paragraph"
        level = None
        text = line
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            title_stack = title_stack[: level - 1] + [text]
            element_type = "title"
        elif re.match(r"^[-*+]\s+", line) or re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^([-*+]|\d+\.)\s+", "", line)
            element_type = "list"
        elif line.startswith("```"):
            element_type = "code"
        elif re.match(r"^!\[.*?\]\(.+?\)$", line):
            element_type = "image"

        metadata = {"parse_source": parse_source, "layout": {}, "figure_refs": []}
        if element_type == "image":
            image_match = re.match(r"^!\[(.*?)\]\((.+?)\)$", line)
            metadata["caption"] = image_match.group(1).strip() if image_match else ""
            metadata["figure_refs"] = [image_match.group(2).strip()] if image_match else []
        elements.append(
            ParsedElement(
                element_id=f"el-{uuid4().hex}",
                type=element_type,
                text=text,
                markdown=line,
                html=html_blocks[html_index] if html_index < len(html_blocks) else "",
                page_start=None,
                page_end=None,
                level=level,
                title_path="/".join(title_stack),
                metadata=metadata,
            )
        )
        html_index += 1

    flush_table()
    if elements:
        return elements
    plain = " ".join(markdown.split())
    return [
        ParsedElement(
            element_id=f"el-{uuid4().hex}",
            type="paragraph",
            text=plain,
            markdown=plain,
            html="",
            page_start=None,
            page_end=None,
            level=None,
            title_path="",
            metadata={"parse_source": parse_source, "layout": {}, "figure_refs": []},
        )
    ] if plain else []


def _looks_like_caption(text: str) -> bool:
    normalized = text.strip().lower()
    return bool(re.match(r"^(table|figure|fig\.|图|表)\s*[-:：]?\s*\S+", normalized))


def _table_text(markdown_table: str) -> str:
    rows = []
    for line in markdown_table.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|") if cell.strip() and set(cell.strip()) != {"-"}]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _table_rows(markdown_table: str) -> list[dict[str, str]]:
    lines = [line for line in markdown_table.splitlines() if line.strip().startswith("|")]
    if not lines:
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|") if cell.strip()]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        row = {}
        for idx, header in enumerate(headers):
            row[header] = cells[idx].strip() if idx < len(cells) else ""
        rows.append(row)
    return rows


def _html_blocks(raw_html: str) -> list[str]:
    parser = _BlockHTMLParser()
    parser.feed(raw_html or "")
    parser.close()
    return parser.blocks


class _BlockHTMLParser(HTMLParser):
    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "li", "pre"}

    def __init__(self):
        super().__init__()
        self.blocks: list[str] = []
        self._current: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self.BLOCK_TAGS and self._depth == 0:
            self._current = [self.get_starttag_text() or f"<{tag}>"]
            self._depth = 1
        elif self._depth:
            self._current.append(self.get_starttag_text() or f"<{tag}>")
            self._depth += 1

    def handle_endtag(self, tag: str):
        if not self._depth:
            return
        self._current.append(f"</{tag}>")
        self._depth -= 1
        if self._depth == 0:
            self.blocks.append("".join(self._current))
            self._current = []

    def handle_data(self, data: str):
        if self._depth:
            self._current.append(html.escape(data))
