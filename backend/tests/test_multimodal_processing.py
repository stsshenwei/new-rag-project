import unittest

from app.models.document_models import ParsedImage
from app.services.documents.multimodal_processing import DisabledOCRProvider, MultimodalResult, image_result_chunk


class MultimodalProcessingTests(unittest.TestCase):
    def test_disabled_provider_reports_unavailable(self):
        provider = DisabledOCRProvider()
        self.assertFalse(provider.available)
        with self.assertRaises(RuntimeError):
            provider.extract_text(b"image", "image/jpeg")

    def test_generated_chunk_keeps_image_and_parent_evidence(self):
        image = ParsedImage("img-1", "kb/img.jpg", "scanned_pdf", page_number=3)
        chunk = image_result_chunk(
            doc_id="doc-1", image=image, result=MultimodalResult("ERROR 42", "fake", 0.9),
            result_type="image_ocr", parent_id="parent-1", scope_metadata={"knowledge_base_id": "kb-1"},
        )
        self.assertEqual("image_ocr", chunk.chunk_type)
        self.assertEqual("parent-1", chunk.parent_id)
        self.assertTrue(chunk.metadata["generated_evidence"])
        self.assertEqual("img-1", chunk.metadata["image_id"])


if __name__ == "__main__":
    unittest.main()
