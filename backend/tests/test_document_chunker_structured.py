import unittest

from app.models.document_models import ParsedDocument, ParsedElement
from app.services.document_chunker import DocumentChunker


def element(idx, type_, text, title_path, level=None, markdown=None, html="", page=1, metadata=None):
    return ParsedElement(
        element_id=f"el-{idx}",
        type=type_,
        text=text,
        markdown=markdown or text,
        html=html,
        page_start=page,
        page_end=page,
        level=level,
        title_path=title_path,
        metadata=metadata or {},
    )


class DocumentChunkerStructuredTests(unittest.TestCase):
    def test_chunker_creates_parent_and_child_chunks_by_heading(self):
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
        self.assertTrue(parents)
        self.assertTrue(children)
        self.assertTrue(all(child.parent_id in {parent.id for parent in parents} for child in children))
        self.assertEqual("第一章", children[0].title_path)

    def test_identical_single_child_is_marked_as_collapsed_but_retrievable(self):
        parsed = ParsedDocument(
            doc_id="doc-collapse",
            file_name="small.md",
            file_type="md",
            elements=[
                element(1, "title", "Guide", "Guide", level=1),
                element(2, "paragraph", "Short body with one retrievable fact.", "Guide"),
            ],
        )

        chunks = DocumentChunker(parent_max_tokens=500, child_max_tokens=500, child_overlap_tokens=10).chunk(parsed)
        parent = next(chunk for chunk in chunks if chunk.chunk_type == "parent")
        child = next(chunk for chunk in chunks if chunk.chunk_type == "child")

        self.assertEqual(parent.content, child.content)
        self.assertEqual(parent.id, child.parent_id)
        self.assertTrue(child.metadata["collapsed_identical_parent"])
        self.assertEqual(parent.id, child.metadata["collapse_parent_id"])

    def test_parent_child_offsets_ids_and_context_headers_are_deterministic(self):
        parsed = ParsedDocument(
            doc_id="doc-guardrail",
            file_name="manual.md",
            file_type="md",
            elements=[
                element(1, "title", "# 第一章 概述", "第一章", level=1, markdown="# 第一章 概述"),
                element(2, "title", "## 接口规格", "第一章 / 接口规格", level=2, markdown="## 接口规格"),
                element(3, "paragraph", "设备提供 8 个 GPON 端口。" * 40, "第一章 / 接口规格"),
                element(4, "title", "## 运维说明", "第一章 / 运维说明", level=2, markdown="## 运维说明"),
                element(5, "paragraph", "升级前需要保存配置。" * 40, "第一章 / 运维说明"),
            ],
        )

        first = DocumentChunker(parent_max_tokens=180, child_max_tokens=80, child_overlap_tokens=10).chunk(parsed)
        second = DocumentChunker(parent_max_tokens=180, child_max_tokens=80, child_overlap_tokens=10).chunk(parsed)
        first_children = [chunk for chunk in first if chunk.chunk_type == "child"]
        second_children = [chunk for chunk in second if chunk.chunk_type == "child"]

        self.assertEqual([chunk.id for chunk in first], [chunk.id for chunk in second])
        self.assertTrue(first_children)
        for child in first_children:
            self.assertTrue(child.parent_id)
            self.assertIn("source_start", child.metadata)
            self.assertIn("source_end", child.metadata)
            self.assertGreaterEqual(child.metadata["source_end"], child.metadata["source_start"])
            self.assertEqual("chars", child.metadata["size_unit"])

        self.assertEqual(
            [(chunk.content, chunk.metadata["source_start"], chunk.metadata["source_end"]) for chunk in first_children],
            [(chunk.content, chunk.metadata["source_start"], chunk.metadata["source_end"]) for chunk in second_children],
        )
        self.assertTrue(any(chunk.metadata.get("context_header") for chunk in first_children))

    def test_table_chunk_preserves_markdown_html_and_builds_embedding_text(self):
        parsed = ParsedDocument(
            doc_id="doc-1",
            file_name="manual.md",
            file_type="md",
            elements=[
                element(1, "title", "第4章", "第4章", level=1),
                element(2, "title", "资源规格", "第4章 / 资源规格", level=2),
                element(3, "paragraph", "下表列出服务器资源规格。", "第4章 / 资源规格"),
                element(
                    4,
                    "table",
                    "CPU 内存 GPU\nKunpeng 920 32*64GB 8卡",
                    "第4章 / 资源规格",
                    markdown="| CPU | 内存 | GPU |\n|---|---|---|\n| Kunpeng 920 | 32*64GB | 8卡 |",
                    html="<table><tr><th>CPU</th><th>内存</th><th>GPU</th></tr></table>",
                    page=22,
                    metadata={"caption": "表4-1 服务器规格"},
                ),
            ],
        )

        table_chunks = [chunk for chunk in DocumentChunker().chunk(parsed) if chunk.chunk_type == "table"]

        self.assertEqual(1, len(table_chunks))
        table = table_chunks[0]
        self.assertIsNotNone(table.parent_id)
        self.assertEqual("第4章 / 资源规格", table.title_path)
        self.assertEqual("表4-1 服务器规格", table.metadata["caption"])
        self.assertIn("| Kunpeng 920 | 32*64GB | 8卡 |", table.content_markdown)
        self.assertIn("CPU", table.metadata["fields"])
        self.assertIn("服务器资源规格", table.metadata["summary"])
        self.assertIn("<table>", table.metadata["llm_context"])
        self.assertIn("表4-1 服务器规格", table.embedding_text)
        self.assertIn("Kunpeng 920", table.embedding_text)


    def test_table_chunk_keeps_rows_counts_and_nearby_text(self):
        parsed = ParsedDocument(
            doc_id="doc-2",
            file_name="manual.md",
            file_type="md",
            elements=[
                element(1, "title", "Manual", "Manual", level=1),
                element(2, "paragraph", "The table lists timeout options.", "Manual"),
                element(
                    3,
                    "table",
                    "Name Value\ntimeout 30",
                    "Manual",
                    markdown="| Name | Value |\n|---|---|\n| timeout | 30 |",
                    html="<table><tr><td>timeout</td><td>30</td></tr></table>",
                    metadata={
                        "caption": "Table 1: Options",
                        "fields": ["Name", "Value"],
                        "rows": [{"Name": "timeout", "Value": "30"}],
                        "row_count": 1,
                        "column_count": 2,
                    },
                ),
            ],
        )

        table = next(chunk for chunk in DocumentChunker().chunk(parsed) if chunk.chunk_type == "table")

        self.assertEqual([{"Name": "timeout", "Value": "30"}], table.metadata["rows"])
        self.assertEqual(1, table.metadata["row_count"])
        self.assertEqual(2, table.metadata["column_count"])
        self.assertIn("The table lists timeout options.", table.metadata["nearby_text"])
        self.assertIn("The table lists timeout options.", table.embedding_text)
        self.assertIn("<table>", table.metadata["llm_context"])

    def test_table_chunk_links_to_matching_parent_not_last_parent(self):
        parsed = ParsedDocument(
            doc_id="doc-table-parent",
            file_name="manual.md",
            file_type="md",
            elements=[
                element(1, "title", "Install", "Install", level=1, page=1),
                element(2, "paragraph", "Install intro.", "Install", page=1),
                element(
                    3,
                    "table",
                    "Name Value\ntimeout 30",
                    "Install",
                    markdown="| Name | Value |\n|---|---|\n| timeout | 30 |",
                    page=1,
                    metadata={"caption": "Install options"},
                ),
                element(4, "title", "Troubleshooting", "Troubleshooting", level=1, page=5),
                element(5, "paragraph", "Troubleshooting intro.", "Troubleshooting", page=5),
            ],
        )

        chunks = DocumentChunker(parent_max_tokens=80, child_max_tokens=80).chunk(parsed)
        table = next(chunk for chunk in chunks if chunk.chunk_type == "table")
        parent = next(chunk for chunk in chunks if chunk.id == table.parent_id)

        self.assertEqual("Install", table.title_path)
        self.assertEqual("Install", parent.title_path)
        self.assertNotEqual("Troubleshooting", parent.title_path)

    def test_ocr_image_element_creates_ocr_chunk_when_confident(self):
        parsed = ParsedDocument(
            doc_id="doc-3",
            file_name="scan.pdf",
            file_type="pdf",
            elements=[
                element(1, "title", "Manual", "Manual", level=1),
                element(
                    2,
                    "image",
                    "ERR_CODE_42 appears on screen",
                    "Manual",
                    metadata={"parse_source": "docling_ocr", "provider": "docling", "confidence": 0.92, "figure_refs": ["page-1-image-1"]},
                ),
            ],
        )

        chunks = DocumentChunker(ocr_min_confidence=0.5).chunk(parsed)
        ocr = next(chunk for chunk in chunks if chunk.chunk_type == "ocr")

        self.assertEqual("ERR_CODE_42 appears on screen", ocr.content)
        self.assertEqual("docling", ocr.metadata["provider"])
        self.assertEqual(0.92, ocr.metadata["confidence"])
        self.assertEqual(["page-1-image-1"], ocr.metadata["figure_refs"])

    def test_low_confidence_ocr_image_is_filtered(self):
        parsed = ParsedDocument(
            doc_id="doc-4",
            file_name="scan.pdf",
            file_type="pdf",
            elements=[
                element(1, "title", "Manual", "Manual", level=1),
                element(2, "image", "unclear", "Manual", metadata={"confidence": 0.1}),
            ],
        )

        chunks = DocumentChunker(ocr_min_confidence=0.5).chunk(parsed)

        self.assertFalse(any(chunk.chunk_type == "ocr" for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
