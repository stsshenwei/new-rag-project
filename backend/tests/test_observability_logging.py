import importlib
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.infrastructure.logging_config import (
    configure_logging_from_env,
    sanitize_payload,
    summarize_body,
    trace_context,
)


class FakeCollection:
    def load(self):
        pass

    def num_entities(self):
        return 0


class FakeRagService:
    def __init__(self, *, fail_delete: bool = False):
        self.fail_delete = fail_delete
        self.agent_trace_stream_enabled = False

    def needs_reingest(self):
        return False

    def resolve_scope(self, knowledge_base_ids=None, document_ids=None):
        from app.models.knowledge_base import KnowledgeBaseScope

        return KnowledgeBaseScope(
            workspace_id="default-workspace",
            selected_knowledge_base_ids=tuple(knowledge_base_ids or ["default-knowledge-base"]),
            document_ids=tuple(document_ids or []),
            compatibility_default=not bool(knowledge_base_ids),
        )

    def delete_document(self, doc_id, scope=None):
        if self.fail_delete:
            raise RuntimeError("delete boom token=secret-value")


class ObservabilityLoggingTests(unittest.TestCase):
    def tearDown(self):
        self.close_log_handlers()

    def close_log_handlers(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                root.removeHandler(handler)

    def test_custom_log_format_writes_trace_id_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "log" / "app.log"
            with patch.dict(
                os.environ,
                {"LOG_LEVEL": "debug", "LOG_PATH": str(log_path), "LOG_FORMAT": "%d %level %traceId %msg"},
                clear=False,
            ):
                configure_logging_from_env()
                with trace_context("trace-123"):
                    logging.getLogger("test.observability").info("hello")
                for handler in logging.getLogger().handlers:
                    handler.flush()

            content = log_path.read_text(encoding="utf-8")
            self.assertIn("INFO trace-123 hello", content)
            self.close_log_handlers()

    def test_invalid_log_level_falls_back_and_logs_without_trace_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "app.log"
            with patch.dict(
                os.environ,
                {"LOG_LEVEL": "very-noisy", "LOG_PATH": str(log_path), "LOG_FORMAT": "%level %traceId %msg"},
                clear=False,
            ):
                configure_logging_from_env()
                logging.getLogger("test.observability").info("outside request")
                for handler in logging.getLogger().handlers:
                    handler.flush()

            content = log_path.read_text(encoding="utf-8")
            self.assertIn("WARNING - Invalid LOG_LEVEL", content)
            self.assertIn("INFO - outside request", content)
            self.close_log_handlers()

    def test_sanitizes_sensitive_fields_and_bounds_bodies(self):
        sanitized = sanitize_payload(
            {
                "api_key": "sk-secret",
                "nested": {"password": "pw", "normal": "ok"},
                "token": "secret-token",
            }
        )
        self.assertEqual("***", sanitized["api_key"])
        self.assertEqual("***", sanitized["nested"]["password"])
        self.assertEqual("***", sanitized["token"])
        self.assertEqual("ok", sanitized["nested"]["normal"])

        summary = summarize_body(b'{"authorization":"Bearer abc","text":"' + b"x" * 3000 + b'"}', "application/json", limit=128)
        self.assertIn("***", summary)
        self.assertIn("[truncated]", summary)

    def import_main(self, tmpdir: str):
        sys.modules.pop("app.main", None)
        env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "",
            "VECTOR_STORE_DIR": str(Path(tmpdir) / "vector_db"),
            "METADATA_DB_PATH": str(Path(tmpdir) / "metadata.sqlite3"),
            "RAG_DATA_DIR": str(Path(tmpdir) / "data"),
            "AUTO_INGEST_ON_STARTUP": "false",
            "LOG_LEVEL": "debug",
            "LOG_PATH": str(Path(tmpdir) / "log" / "app.log"),
            "LOG_FORMAT": "%level %traceId %msg",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
                return importlib.import_module("app.main")

    def test_request_trace_id_header_is_returned_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self.import_main(tmp)
            module.rag_service = FakeRagService()
            with TestClient(module.app) as client:
                response = client.get("/health", headers={"X-Trace-ID": "trace-from-client"})

            self.assertEqual(200, response.status_code)
            self.assertEqual("trace-from-client", response.headers["X-Trace-ID"])
            content = (Path(tmp) / "log" / "app.log").read_text(encoding="utf-8")
            self.assertIn("trace-from-client request.start", content)
            self.assertIn("trace-from-client request.end", content)
            self.close_log_handlers()

    def test_failing_request_writes_traceback_to_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self.import_main(tmp)
            module.rag_service = FakeRagService(fail_delete=True)
            with TestClient(module.app) as client:
                response = client.delete("/rag/documents/doc-1", headers={"X-Request-ID": "delete-trace"})

            self.assertEqual(500, response.status_code)
            self.assertEqual("delete-trace", response.headers["X-Trace-ID"])
            content = (Path(tmp) / "log" / "app.log").read_text(encoding="utf-8")
            self.assertIn("delete-trace Failed to delete document", content)
            self.assertIn("RuntimeError: delete boom", content)
            self.assertNotIn("secret-value", content)
            self.close_log_handlers()


if __name__ == "__main__":
    unittest.main()
