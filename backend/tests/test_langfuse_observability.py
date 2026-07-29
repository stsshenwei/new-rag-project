import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.retrieval.embedding_provider import OpenAIEmbeddingProvider
from app.services.infrastructure.observability import (
    LangfuseObservabilitySink,
    NoopObservabilitySink,
    ObservabilityConfig,
    ObservationHandle,
    ObservabilitySink,
    configure_observability_from_env,
    sanitize_observability_payload,
    set_observability_sink,
)
from app.services.processing.processing_trace import ProcessingTraceRecorder
from app.services.retrieval.rag_service import RAGService
from app.services.retrieval.reranker import DashScopeReranker


class RecordingGeneration:
    def __init__(self, sink, name, input, model=""):
        self.sink = sink
        self.name = name
        self.model = model
        self.input = input

    def finish(self, *, output=None, metadata=None, error=None, usage=None):
        self.sink.finished.append(
            {
                "name": self.name,
                "model": self.model,
                "input": self.input,
                "output": output,
                "error": error,
                "usage": usage,
            }
        )


class RecordingSink(ObservabilitySink):
    def __init__(self):
        self.started = []
        self.finished = []
        self.flushed = 0

    def start_generation(self, *, name, model, input=None, metadata=None, model_parameters=None):
        self.started.append({"name": name, "model": model, "input": input, "metadata": metadata})
        return ObservationHandle(self, raw=RecordingGeneration(self, name, input, model=model), observation_id=name)

    def start_span(self, *, name, input=None, metadata=None):
        self.started.append({"name": name, "type": "span", "input": input, "metadata": metadata})
        return ObservationHandle(self, raw=RecordingGeneration(self, name, input), observation_id=name)

    def finish_observation(self, handle, *, output=None, metadata=None, error=None, usage=None):
        raw = handle.raw
        self.finished.append(
            {
                "name": raw.name,
                "model": raw.model,
                "input": raw.input,
                "output": output,
                "error": error,
                "usage": usage,
            }
        )

    def flush(self):
        self.flushed += 1


class FakeEmbeddings:
    def create(self, model, input):
        if isinstance(input, str):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0, 3.0])])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[float(i), 2.0]) for i, _ in enumerate(input)])


class FakeClient:
    embeddings = FakeEmbeddings()


class FakeVectorStore:
    def __init__(self):
        self.persist_dir = Path(tempfile.mkdtemp())

    def count(self):
        return 0

    def query(self, question, top_k):
        return [
            {
                "content": "raw document body " * 200,
                "metadata": {"chunk_id": "c1", "doc_id": "doc-1", "parent_id": "p1"},
                "distance": 0.1,
            }
        ]

    def query_dense(self, question, top_k):
        return self.query(question, top_k)

    def query_bm25(self, question, top_k):
        return []


class FakeStreamingCompletions:
    def create(self, **kwargs):
        delta = SimpleNamespace(content="answer")
        choice = SimpleNamespace(delta=delta)
        return [SimpleNamespace(choices=[choice])]


class FakeStreamingClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeStreamingCompletions())


class BrokenFlushClient:
    def flush(self):
        raise RuntimeError("flush failed")


class FakeHTTPResponse:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class LangfuseObservabilityTests(unittest.TestCase):
    def tearDown(self):
        set_observability_sink(NoopObservabilitySink())

    def test_base_url_precedes_host(self):
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_ENABLED": "true",
                "LANGFUSE_BASE_URL": "http://localhost:3001",
                "LANGFUSE_HOST": "http://wrong-host:3000",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
            },
            clear=False,
        ):
            config = ObservabilityConfig.from_env()

        self.assertTrue(config.enabled)
        self.assertEqual("http://localhost:3001", config.host)
        self.assertTrue(config.configured)

    def test_missing_credentials_uses_noop_status(self):
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "true", "LANGFUSE_BASE_URL": "http://localhost:3001"}, clear=True):
            sink = configure_observability_from_env()

        status = sink.status().to_dict()
        self.assertTrue(status["enabled"])
        self.assertFalse(status["configured"])
        self.assertEqual("missing credentials", status["reason"])

    def test_missing_package_is_reported_without_raising(self):
        config = ObservabilityConfig(enabled=True, host="http://localhost:3001", public_key="pk", secret_key="sk")
        sink = LangfuseObservabilitySink(config)

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "langfuse":
                raise ImportError("missing langfuse")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            handle = sink.start_trace(name="request")

        self.assertIsNone(handle.raw)
        status = sink.status().to_dict()
        self.assertFalse(status["package_available"])
        self.assertTrue(status["failed"])
        self.assertIn("package unavailable", status["reason"])

    def test_failed_client_initialization_and_flush_are_safe(self):
        def raise_on_init(**kwargs):
            raise RuntimeError("server unavailable")

        config = ObservabilityConfig(enabled=True, host="http://localhost:3001", public_key="pk", secret_key="sk")
        sink = LangfuseObservabilitySink(config)
        with patch.dict(sys.modules, {"langfuse": SimpleNamespace(Langfuse=raise_on_init)}):
            handle = sink.start_trace(name="request")

        self.assertIsNone(handle.raw)
        self.assertTrue(sink.status().failed)

        flush_sink = LangfuseObservabilitySink(config)
        flush_sink._client = BrokenFlushClient()
        flush_sink.flush()
        self.assertTrue(flush_sink.status().failed)

    def test_sanitizes_sensitive_and_long_payloads(self):
        payload = sanitize_observability_payload(
            {
                "Authorization": "Bearer token-value",
                "normal": "x" * 20,
                "content": "y" * 300,
                "nested": {"api_key": "sk-secret"},
            },
            limit=32,
        )

        self.assertEqual("[redacted]", payload["Authorization"])
        self.assertEqual("[redacted]", payload["nested"]["api_key"])
        self.assertIn("[truncated]", payload["content"])

    def test_embedding_provider_emits_generation(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        provider = OpenAIEmbeddingProvider(client=FakeClient(), model="embedding-model")

        self.assertEqual([1.0, 2.0, 3.0], provider.embed_text("hello"))

        self.assertEqual("embedding.embed", sink.started[0]["name"])
        self.assertEqual("embedding-model", sink.started[0]["model"])
        self.assertEqual(3, sink.finished[0]["output"]["dimensions"])

    def test_dashscope_reranker_emits_generation(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        reranker = DashScopeReranker(model="rerank-model", api_key="test-key")

        def fake_urlopen(request, timeout):
            return FakeHTTPResponse('{"output":{"results":[{"index":0,"relevance_score":0.9}]}}')

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ranked = reranker.rerank("question", [{"content": "evidence", "metadata": {"chunk_id": "c1"}}], top_k=1)

        self.assertEqual("evidence", ranked[0]["content"])
        self.assertEqual("rerank", sink.started[0]["name"])
        self.assertEqual("rerank-model", sink.started[0]["model"])
        self.assertEqual("c1", sink.finished[0]["output"]["top_hits"][0]["chunk_id"])

    def test_stream_answer_emits_chat_generation(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        service = RAGService(
            vector_store=FakeVectorStore(),
            llm_client=FakeStreamingClient(),
            chat_model="chat-model",
            system_prompt="system",
            data_dir=tempfile.mkdtemp(),
            top_k=3,
            min_relevance_score=0.0,
            chunk_size=80,
            chunk_overlap=10,
        )

        answer = "".join(service.stream_answer("question", hits=[{"content": "context", "metadata": {"source": "manual.md"}}]))

        self.assertEqual("answer", answer)
        self.assertEqual("chat.completion.stream", sink.started[0]["name"])
        self.assertEqual("chat-model", sink.started[0]["model"])
        self.assertEqual("answer", sink.finished[0]["output"]["content"])

    def test_retrieval_span_uses_safe_summaries(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        service = RAGService(
            vector_store=FakeVectorStore(),
            llm_client=SimpleNamespace(),
            chat_model="chat-model",
            system_prompt="system",
            data_dir=tempfile.mkdtemp(),
            top_k=1,
            min_relevance_score=0.0,
            chunk_size=80,
            chunk_overlap=10,
        )

        hits = service.hybrid_retrieve_hits("question")

        self.assertEqual(1, len(hits))
        self.assertEqual("retrieval.hybrid", sink.started[0]["name"])
        output_text = str(sink.finished[0]["output"])
        self.assertIn("c1", output_text)
        self.assertNotIn("raw document body raw document body raw document body", output_text)

    def test_processing_trace_recorder_emits_document_spans(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = ProcessingTraceRecorder.from_env(tmpdir)
            trace = recorder.start(
                name="document.processing",
                doc_id="doc-1",
                file_name="sample.txt",
                source="upload",
                scope={"knowledge_base_id": "kb-1"},
                metadata={"task_id": "task-1"},
            )
            with trace.span("load", input={"extension": ".txt"}) as span:
                trace.record_output(span, {"parser": "text", "text_chars": 12})
            trace.finish(status="completed")

        names = [item["name"] for item in sink.started]
        self.assertIn("document.processing", names)
        self.assertIn("document.docreader", names)
        self.assertGreaterEqual(sink.flushed, 1)

    def test_processing_trace_recorder_marks_failed_stage(self):
        sink = RecordingSink()
        set_observability_sink(sink)
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = ProcessingTraceRecorder.from_env(tmpdir)
            trace = recorder.start(
                name="document.processing",
                doc_id="doc-1",
                file_name="broken.txt",
                source="upload",
                scope={"knowledge_base_id": "kb-1"},
            )
            with self.assertRaises(ValueError):
                with trace.span("load", input={"extension": ".txt"}):
                    raise ValueError("parse failed because file is invalid")
            trace.finish(status="failed", error=ValueError("parse failed because file is invalid"))

        failed = [item for item in sink.finished if item["error"] is not None]
        self.assertGreaterEqual(len(failed), 1)
        self.assertIn("document.docreader", {item["name"] for item in failed})


if __name__ == "__main__":
    unittest.main()
