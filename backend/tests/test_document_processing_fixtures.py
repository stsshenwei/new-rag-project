import json
import unittest
from pathlib import Path

from app.services.documents.adaptive_chunker import AdaptiveChunkConfig, profile_document, split_with_diagnostics


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "document_processing_cases.json"


class DocumentProcessingFixtureTests(unittest.TestCase):
    def test_safe_fixture_expected_diagnostics(self):
        cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "native_pdf",
                "scanned_pdf",
                "hybrid_pdf",
                "structured_markdown",
                "heuristic_sections",
                "unstructured_plain",
                "markdown_table",
                "code_block",
                "cjk_prose",
            },
            {case["id"] for case in cases},
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                if case["kind"] == "pdf_diagnostics":
                    expected = case["expected"]
                    self.assertEqual(
                        expected["page_count"],
                        expected["text_page_count"] + expected["scanned_page_count"],
                    )
                    self.assertIn(expected["source_classification"], {"native", "scanned", "hybrid"})
                    continue

                text = case["content"]
                expected = case["expected"]
                profile = profile_document(text)
                _, diagnostics = split_with_diagnostics(
                    text,
                    AdaptiveChunkConfig(chunk_size_chars=160, chunk_overlap_chars=20, strategy="auto"),
                )
                for key, value in expected.items():
                    if key == "dominant_heading_level":
                        self.assertEqual(value, profile.dominant_heading_level())
                    elif key == "tier_chain":
                        self.assertEqual(value, diagnostics.tier_chain)
                    elif key == "selected_tier":
                        self.assertEqual(value, diagnostics.selected_tier)
                    elif key == "detected_languages":
                        self.assertEqual(tuple(value), profile.detected_languages)
                    else:
                        self.assertEqual(value, getattr(profile, key))


if __name__ == "__main__":
    unittest.main()
