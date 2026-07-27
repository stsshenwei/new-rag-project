import unittest

from app.models.document_models import Chunk, ParsedDocument, ParsedElement
from app.models.processing_config import PROCESSING_VERSION


class DocumentModelTests(unittest.TestCase):
    def test_parsed_document_contains_required_element_fields(self):
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
        parsed = ParsedDocument(doc_id="doc-1", file_name="manual.pdf", file_type="pdf", elements=[element])

        self.assertEqual("doc-1", parsed.doc_id)
        self.assertEqual("title", parsed.elements[0].type)
        self.assertEqual("安装说明", parsed.elements[0].title_path)

    def test_table_chunk_embedding_text_uses_caption_summary_and_markdown(self):
        chunk = Chunk(
            id="table-1",
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_type="table",
            title_path="第4章 / 资源规格",
            content="CPU 内存 GPU\nKunpeng 920 32*64GB 8卡",
            content_markdown="| CPU | 内存 | GPU |\n|---|---|---|\n| Kunpeng 920 | 32*64GB | 8卡 |",
            page_start=22,
            page_end=22,
            token_count=20,
            metadata={"caption": "表4-1 服务器规格", "summary": "该表描述服务器资源规格", "fields": ["CPU", "内存", "GPU"]},
        )

        self.assertIn("第4章 / 资源规格", chunk.embedding_text)
        self.assertIn("表4-1 服务器规格", chunk.embedding_text)
        self.assertIn("该表描述服务器资源规格", chunk.embedding_text)
        self.assertIn("| Kunpeng 920 | 32*64GB | 8卡 |", chunk.embedding_text)

    def test_chunk_embedding_uses_context_header_without_changing_content(self):
        chunk = Chunk(
            id="child-1",
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_type="child",
            title_path="Guide / Install",
            content="Run the installer.",
            content_markdown="Run the installer.",
            page_start=1,
            page_end=1,
            token_count=4,
            metadata={"context_header": "# Guide\n## Install"},
        )

        self.assertEqual("Run the installer.", chunk.content)
        self.assertIn("# Guide\n## Install", chunk.embedding_text)
        self.assertIn("Run the installer.", chunk.embedding_text)

    def test_chunk_provenance_properties_read_metadata_defaults(self):
        image_chunk = Chunk(
            id="img-1",
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_type="image_ocr",
            title_path="Manual",
            content="Detected text",
            content_markdown="Detected text",
            page_start=3,
            page_end=3,
            token_count=3,
            metadata={
                "strategy": "image_ocr",
                "image_id": "page-3-image-1",
                "storage_key": "media/page-3-image-1.jpg",
                "source_type": "scanned_page",
                "provider": "fake-ocr",
                "confidence": 0.88,
            },
        )

        self.assertEqual("image_ocr", image_chunk.strategy)
        self.assertEqual(PROCESSING_VERSION, image_chunk.processing_version)
        self.assertEqual("chars", image_chunk.size_unit)
        self.assertEqual("page-3-image-1", image_chunk.image_id)
        self.assertEqual("media/page-3-image-1.jpg", image_chunk.storage_key)
        self.assertEqual("scanned_page", image_chunk.image_provenance["source_type"])


if __name__ == "__main__":
    unittest.main()
