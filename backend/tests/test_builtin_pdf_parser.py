import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from app.models.processing_config import ParserErrorCode
from app.services import document_parser
from app.services.document_parser import BuiltinPDFParser, ParserError, _select_native_pdf_text


class BuiltinPDFParserTests(unittest.TestCase):
    def test_mixed_pdf_routes_native_and_scanned_pages_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.pdf"
            pdf = fitz.open()
            text_page = pdf.new_page(width=300, height=400)
            text_page.insert_text((30, 40), "NATIVE TEXT PAGE WITH ENOUGH CONTENT FOR CLASSIFICATION")
            image = Image.new("RGB", (600, 800), "white")
            ImageDraw.Draw(image).text((40, 40), "SCANNED PAGE", fill="black")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG")
            scan_page = pdf.new_page(width=300, height=400)
            scan_page.insert_image(scan_page.rect, stream=buffer.getvalue())
            pdf.save(path)
            pdf.close()

            parsed = BuiltinPDFParser(render_dpi=100).parse(path)

        self.assertEqual(2, parsed.metadata["page_count"])
        self.assertEqual(1, parsed.metadata["text_page_count"])
        self.assertEqual(1, parsed.metadata["scanned_page_count"])
        self.assertIn("NATIVE TEXT PAGE", parsed.markdown)
        self.assertIn("mixed_page_2.jpg", parsed.markdown)
        self.assertEqual("scanned_pdf", parsed.images[-1].source_type)
        self.assertEqual("hybrid", parsed.metadata["source_classification"])
        self.assertEqual(2, parsed.metadata["text_page_count"] + parsed.metadata["scanned_page_count"])

    def test_force_scanned_renders_all_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "native.pdf"
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((30, 40), "A native text page with enough content to extract")
            pdf.save(path)
            pdf.close()
            parsed = BuiltinPDFParser(force_scanned=True, render_dpi=80).parse(path)
        self.assertEqual(1, parsed.metadata["scanned_page_count"])
        self.assertEqual(0, parsed.metadata["text_page_count"])
        self.assertEqual("scanned", parsed.metadata["source_classification"])

    def test_native_pdf_promotes_headings_and_strips_repeating_header_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "native.pdf"
            pdf = fitz.open()
            for page_index in range(4):
                page = pdf.new_page(width=300, height=400)
                page.insert_text((30, 30), "REPORT HEADER")
                page.insert_text((30, 80), f"1.{page_index + 1} Native section")
                page.insert_text((30, 120), f"Body text for page {page_index + 1} with enough useful words.")
                page.insert_text((30, 360), "CONFIDENTIAL FOOTER")
            pdf.save(path)
            pdf.close()

            parsed = BuiltinPDFParser(render_dpi=80).parse(path)

        self.assertEqual(4, parsed.metadata["text_page_count"])
        self.assertNotIn("REPORT HEADER", parsed.markdown)
        self.assertNotIn("CONFIDENTIAL FOOTER", parsed.markdown)
        self.assertIn("## 1.1 Native section", parsed.markdown)
        self.assertIn("Body text for page 4", parsed.markdown)

    def test_scanned_pdf_render_obeys_max_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scanned.pdf"
            pdf = fitz.open()
            image = Image.new("RGB", (1200, 1600), "white")
            ImageDraw.Draw(image).text((80, 80), "SCANNED ONLY", fill="black")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG")
            for _ in range(2):
                page = pdf.new_page(width=300, height=400)
                page.insert_image(page.rect, stream=buffer.getvalue())
            pdf.save(path)
            pdf.close()

            parsed = BuiltinPDFParser(render_dpi=200, max_image_edge_px=128, render_concurrency=1).parse(path)

        self.assertEqual(2, parsed.metadata["scanned_page_count"])
        self.assertTrue(all(max(image.width or 0, image.height or 0) <= 256 for image in parsed.images))
        self.assertEqual(256, parsed.metadata["pdf_max_image_edge_px"])
        self.assertEqual(1, parsed.metadata["pdf_render_concurrency"])

    def test_malformed_text_layer_prefers_layout_when_quality_is_better(self):
        plain = "T\nh\ni\ns\n\nI\ns\n\nB\na\nd"
        layout = "This Is Better Ordered Text"

        text, used_layout = _select_native_pdf_text(plain, layout)

        self.assertTrue(used_layout)
        self.assertEqual(layout, text)

    def test_native_page_extracts_embedded_and_vector_figures_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figures.pdf"
            pdf = fitz.open()
            page = pdf.new_page(width=300, height=400)
            page.insert_text((30, 40), "A native page with figures and enough text for classification.")
            page.draw_rect(fitz.Rect(40, 120, 220, 260), color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
            image = Image.new("RGB", (200, 120), "white")
            ImageDraw.Draw(image).rectangle((20, 20, 180, 100), outline="black")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG")
            page.insert_image(fitz.Rect(50, 280, 180, 360), stream=buffer.getvalue())
            pdf.save(path)
            pdf.close()

            parsed = BuiltinPDFParser(render_dpi=100, max_image_edge_px=256).parse(path)

        source_types = {image.source_type for image in parsed.images}
        self.assertIn("embedded_image", source_types)
        self.assertIn("vector_figure", source_types)
        self.assertGreaterEqual(parsed.metadata["embedded_image_count"], 1)
        self.assertGreaterEqual(parsed.metadata["vector_figure_count"], 1)
        self.assertTrue(all("page_position" in image.metadata for image in parsed.images))

    def test_page_limit_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "too_many.pdf"
            pdf = fitz.open()
            pdf.new_page().insert_text((30, 40), "Page one with text")
            pdf.new_page().insert_text((30, 40), "Page two with text")
            pdf.save(path)
            pdf.close()

            with self.assertRaises(ParserError) as ctx:
                BuiltinPDFParser(max_pages=1).parse(path)

        self.assertEqual(ParserErrorCode.PDF_PAGE_LIMIT_EXCEEDED.value, ctx.exception.code)

    def test_password_protected_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "protected.pdf"
            pdf = fitz.open()
            pdf.new_page().insert_text((30, 40), "Secret text")
            pdf.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
            pdf.close()

            with self.assertRaises(ParserError) as ctx:
                BuiltinPDFParser().parse(path)

        self.assertIn(ctx.exception.code, {ParserErrorCode.PDF_PASSWORD_REQUIRED.value, ParserErrorCode.PDF_OPEN_FAILED.value})

    def test_unexpected_routing_failure_uses_render_all_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fallback.pdf"
            pdf = fitz.open()
            pdf.new_page().insert_text((30, 40), "Native text that can be rendered after fallback")
            pdf.save(path)
            pdf.close()

            original = document_parser._pdf_page_image_area_ratio
            calls = {"count": 0}

            def fail_once(page):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("route failed")
                return original(page)

            document_parser._pdf_page_image_area_ratio = fail_once
            try:
                parsed = BuiltinPDFParser(render_dpi=80).parse(path)
            finally:
                document_parser._pdf_page_image_area_ratio = original

        self.assertTrue(parsed.metadata["render_all_fallback"])
        self.assertEqual("render_all_after_routing_failure", parsed.diagnostics.fallback_reason)
        self.assertEqual(1, parsed.metadata["scanned_page_count"])

    def test_concurrent_pdf_parses_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "concurrent.pdf"
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((30, 40), "Concurrent native PDF parse text with enough content")
            pdf.save(path)
            pdf.close()

            def parse_once():
                return BuiltinPDFParser(render_dpi=80, render_concurrency=1).parse(path).metadata

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: parse_once(), range(4)))

        self.assertTrue(all(result["page_count"] == 1 for result in results))
        self.assertTrue(all(result["text_page_count"] == 1 for result in results))


if __name__ == "__main__":
    unittest.main()
