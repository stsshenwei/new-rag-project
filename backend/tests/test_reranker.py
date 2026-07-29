import unittest
from unittest.mock import patch

from app.services.retrieval.reranker import DashScopeReranker, NoOpReranker, build_reranker


class FakeHTTPResponse:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class RerankerTests(unittest.TestCase):
    def test_build_reranker_returns_noop_when_disabled(self):
        reranker = build_reranker(enabled=False)

        chunks = [{"content": "a"}, {"content": "b"}]
        self.assertIsInstance(reranker, NoOpReranker)
        self.assertEqual([{"content": "a"}], reranker.rerank("q", chunks, top_k=1))

    def test_build_reranker_falls_back_to_noop_when_local_dependency_missing(self):
        reranker = build_reranker(enabled=True, provider="local", model="missing-model")

        self.assertIsInstance(reranker, NoOpReranker)

    def test_build_reranker_falls_back_to_noop_for_unknown_provider(self):
        reranker = build_reranker(enabled=True, provider="unknown", model="unused")

        self.assertIsInstance(reranker, NoOpReranker)

    def test_build_reranker_creates_dashscope_provider_with_key(self):
        reranker = build_reranker(
            enabled=True,
            provider="dashscope",
            model="qwen3-vl-rerank",
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        )

        self.assertIsInstance(reranker, DashScopeReranker)
        self.assertEqual("qwen3-vl-rerank", reranker.model_name)

    def test_build_reranker_falls_back_when_dashscope_key_missing(self):
        with patch.dict("os.environ", {"RERANKER_API_KEY": "", "DASHSCOPE_API_KEY": ""}):
            reranker = build_reranker(enabled=True, provider="dashscope", model="qwen3-vl-rerank", api_key="")

        self.assertIsInstance(reranker, NoOpReranker)

    def test_dashscope_reranker_orders_by_remote_scores(self):
        reranker = DashScopeReranker(model="qwen3-vl-rerank", api_key="test-key", timeout_seconds=1)
        chunks = [{"content": "first", "metadata": {"chunk_id": "a"}}, {"content": "second", "metadata": {"chunk_id": "b"}}]

        def fake_urlopen(request, timeout):
            body = request.data.decode("utf-8")
            self.assertIn('"model": "qwen3-vl-rerank"', body)
            self.assertIn('"query": "question"', body)
            self.assertIn('"documents": ["first", "second"]', body)
            self.assertEqual(1, timeout)
            self.assertEqual("Bearer test-key", request.headers["Authorization"])
            return FakeHTTPResponse('{"output":{"results":[{"index":1,"relevance_score":0.91},{"index":0,"relevance_score":0.12}]}}')

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ranked = reranker.rerank("question", chunks, top_k=2)

        self.assertEqual(["second", "first"], [item["content"] for item in ranked])
        self.assertEqual([0.91, 0.12], [item["reranker_score"] for item in ranked])

    def test_dashscope_reranker_excludes_empty_documents_and_preserves_mapping(self):
        reranker = DashScopeReranker(model="qwen3-vl-rerank", api_key="test-key")
        chunks = [
            {"content": "", "metadata": {"chunk_id": "empty"}},
            {"content": "useful evidence", "metadata": {"chunk_id": "useful"}},
        ]

        def fake_urlopen(request, timeout):
            body = request.data.decode("utf-8")
            self.assertIn('"documents": ["useful evidence"]', body)
            self.assertNotIn('"documents": [""', body)
            return FakeHTTPResponse('{"output":{"results":[{"index":0,"relevance_score":0.91}]}}')

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ranked = reranker.rerank("question", chunks, top_k=2)

        self.assertEqual("useful", ranked[0]["metadata"]["chunk_id"])
        self.assertEqual(0.91, ranked[0]["reranker_score"])

    def test_dashscope_reranker_skips_request_when_all_documents_are_empty(self):
        reranker = DashScopeReranker(model="qwen3-vl-rerank", api_key="test-key")
        chunks = [{"content": "", "metadata": {"chunk_id": "empty"}}]

        with patch("urllib.request.urlopen") as urlopen:
            ranked = reranker.rerank("question", chunks, top_k=1)

        urlopen.assert_not_called()
        self.assertEqual(chunks, ranked)


if __name__ == "__main__":
    unittest.main()
