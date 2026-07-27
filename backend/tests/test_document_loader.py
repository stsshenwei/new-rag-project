import tempfile
import unittest
from pathlib import Path

from app.services.document_loader import (
    SUPPORTED_EXTS,
    build_parent_child_chunks,
    iter_source_files,
    load_text,
)


class DocumentLoaderTests(unittest.TestCase):
    def test_supported_extensions_include_requested_document_types(self):
        self.assertIn(".pdf", SUPPORTED_EXTS)
        self.assertIn(".docx", SUPPORTED_EXTS)
        self.assertIn(".html", SUPPORTED_EXTS)
        self.assertIn(".htm", SUPPORTED_EXTS)
        self.assertIn(".xlsx", SUPPORTED_EXTS)
        self.assertIn(".xlsm", SUPPORTED_EXTS)
        self.assertIn(".md", SUPPORTED_EXTS)

    def test_iter_source_files_excludes_processing_traces(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "manual.md").write_text("# Manual", encoding="utf-8")
            trace_dir = base / "processing_traces" / "20260718" / "manual-trace"
            trace_dir.mkdir(parents=True)
            (trace_dir / "parsed.md").write_text("# Trace artifact", encoding="utf-8")
            (trace_dir / "trace.json").write_text("{}", encoding="utf-8")

            files = {path.relative_to(base).as_posix() for path in iter_source_files(base)}

        self.assertEqual({"manual.md"}, files)

    def test_load_text_extracts_visible_html_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.html"
            path.write_text(
                "<html><head><style>.x{}</style><script>ignore()</script></head>"
                "<body><h1>标题</h1><p>第一段内容</p><div>第二段内容</div></body></html>",
                encoding="utf-8",
            )

            text = load_text(path)

        self.assertIn("标题", text)
        self.assertIn("第一段内容", text)
        self.assertIn("第二段内容", text)
        self.assertNotIn("ignore()", text)

    def test_build_parent_child_chunks_links_children_to_parent_text(self):
        text = "甲" * 90 + "乙" * 90 + "丙" * 90

        chunks = build_parent_child_chunks(
            source="sample.md",
            text=text,
            parent_size=120,
            parent_overlap=20,
            child_size=50,
            child_overlap=10,
        )

        self.assertGreater(len(chunks), 1)
        self.assertEqual("sample.md", chunks[0].source)
        self.assertTrue(chunks[0].parent_id.startswith("sample.md::parent-"))
        self.assertTrue(chunks[0].child_id.startswith(chunks[0].parent_id + "::child-"))
        self.assertIn(chunks[0].child_text, chunks[0].parent_text)


if __name__ == "__main__":
    unittest.main()
