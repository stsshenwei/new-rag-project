import unittest

from app.models.processing_config import (
    PROCESSING_VERSION,
    ChunkStrategy,
    DurableProcessingWorkerConfig,
    ParserErrorCode,
    ProcessingRuntimeDefaults,
    resolve_processing_config,
)


class ProcessingConfigTests(unittest.TestCase):
    def test_resolved_config_reports_requested_and_effective_values(self):
        resolved = resolve_processing_config(
            {
                "parser_engine": "missing",
                "chunk_strategy": "semantic",
                "ocr_enabled": True,
                "caption_enabled": True,
                "child_chunk_size_chars": 100,
                "child_chunk_overlap_chars": 80,
                "pdf_render_dpi": 900,
                "pdf_jpeg_quality": 200,
            },
            ProcessingRuntimeDefaults(),
            available_parser_engines={"builtin"},
            caption_available=False,
        )

        self.assertEqual("missing", resolved.requested.parser_engine)
        self.assertEqual("builtin", resolved.effective.parser_engine)
        self.assertEqual(ChunkStrategy.AUTO.value, resolved.effective.chunk_strategy)
        self.assertEqual(50, resolved.effective.child_chunk_overlap_chars)
        self.assertEqual(600, resolved.effective.pdf_render_dpi)
        self.assertEqual(95, resolved.effective.pdf_jpeg_quality)
        self.assertFalse(resolved.effective.ocr_enabled)
        self.assertFalse(resolved.effective.caption_enabled)
        self.assertEqual(PROCESSING_VERSION, resolved.effective.processing_version)
        self.assertIn("parser_engine", resolved.effective.inactive_overrides)
        self.assertIn("chunk_strategy", resolved.effective.inactive_overrides)

    def test_stable_error_code_values_are_explicit(self):
        self.assertEqual("UNSUPPORTED_FORMAT", ParserErrorCode.UNSUPPORTED_FORMAT.value)
        self.assertEqual("PDF_PAGE_LIMIT_EXCEEDED", ParserErrorCode.PDF_PAGE_LIMIT_EXCEEDED.value)

    def test_durable_processing_worker_config_normalizes_settings(self):
        config = DurableProcessingWorkerConfig.from_settings(
            {
                "enabled": "true",
                "poll_interval_seconds": "0",
                "lease_timeout_seconds": "0",
                "max_concurrent_tasks": "0",
                "retry_backoff_seconds": "1, 5, 20",
                "parser_max_attempts": "4",
            }
        )

        self.assertTrue(config.enabled)
        self.assertEqual(0.1, config.poll_interval_seconds)
        self.assertEqual(1, config.lease_timeout_seconds)
        self.assertEqual(1, config.max_concurrent_tasks)
        self.assertEqual((1, 5, 20), config.retry_backoff_seconds)
        self.assertEqual(4, config.max_attempts_for_stage("parse"))
        self.assertEqual(config.embedding_max_attempts, config.max_attempts_for_stage("embedding"))
        self.assertEqual(config.default_max_attempts, config.max_attempts_for_stage("unknown"))
        self.assertEqual(20, config.retry_delay_for_attempt(99))


if __name__ == "__main__":
    unittest.main()
