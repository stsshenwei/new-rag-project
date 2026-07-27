import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.rag_config import load_rag_config


class RagConfigTests(unittest.TestCase):
    def test_load_rag_config_resolves_env_and_merges_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag.yaml"
            path.write_text(
                """
rag:
  embedding:
    provider: qwen
    api_key: ${EMBEDDING_API_KEY}
  vector_store:
    type: milvus
    url: ${MILVUS_URI}
  keyword_search:
    type: milvus
  retrieval:
    dense_top_k: 11
    keyword_top_k: 13
    fusion_top_k: 17
    rerank_top_k: 7
  context:
    max_tokens: 4096
    include_neighbor_chunks: false
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"EMBEDDING_API_KEY": "embed-key", "MILVUS_URI": "http://127.0.0.1:19530"}):
                config = load_rag_config(path)

        rag = config["rag"]
        self.assertEqual("qwen", rag["embedding"]["provider"])
        self.assertEqual("embed-key", rag["embedding"]["api_key"])
        self.assertEqual("milvus", rag["keyword_search"]["type"])
        self.assertEqual("http://127.0.0.1:19530", rag["vector_store"]["url"])
        self.assertEqual(11, rag["retrieval"]["dense_top_k"])
        self.assertEqual(13, rag["retrieval"]["keyword_top_k"])
        self.assertEqual(17, rag["retrieval"]["fusion_top_k"])
        self.assertEqual(7, rag["retrieval"]["rerank_top_k"])
        self.assertEqual(60, rag["retrieval"]["rrf_k"])
        self.assertEqual(0.7, rag["retrieval"]["rrf_vector_weight"])
        self.assertEqual(0.3, rag["retrieval"]["rrf_keyword_weight"])
        self.assertEqual(0.3, rag["retrieval"]["reranker_threshold"])
        self.assertEqual(0.15, rag["retrieval"]["reranker_fallback_min_score"])
        self.assertTrue(rag["retrieval"]["reranker_degradation_enabled"])
        self.assertEqual(0.15, rag["retrieval"]["reranker_degraded_threshold"])
        self.assertEqual(1, rag["retrieval"]["reranker_fallback_top_n"])
        self.assertFalse(rag["retrieval"]["low_recall_query_expansion_enabled"])
        self.assertEqual(3, rag["retrieval"]["low_recall_min_candidates"])
        self.assertEqual(0.2, rag["retrieval"]["low_recall_min_score"])
        self.assertEqual(3, rag["retrieval"]["low_recall_max_queries"])
        self.assertFalse(rag["retrieval"]["mmr_enabled"])
        self.assertEqual(0.75, rag["retrieval"]["mmr_lambda"])
        self.assertEqual(0, rag["retrieval"]["mmr_top_k"])
        self.assertEqual(0.92, rag["retrieval"]["duplicate_overlap_threshold"])
        self.assertEqual(50, rag["retrieval"]["direct_load_max_chunks"])
        self.assertEqual(4096, rag["context"]["max_tokens"])
        self.assertFalse(rag["context"]["include_neighbor_chunks"])
        self.assertEqual(240, rag["context"]["short_chunk_min_chars"])
        self.assertEqual(1200, rag["context"]["expanded_chunk_max_chars"])
        self.assertIn("llm", rag)

    def test_default_config_keeps_env_compatibility(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key", "MILVUS_URI": "http://127.0.0.1:19530"}):
            config = load_rag_config()

        self.assertEqual("key", config["rag"]["embedding"]["api_key"])
        self.assertEqual("milvus", config["rag"]["keyword_search"]["type"])
        self.assertEqual(50, config["rag"]["retrieval"]["dense_top_k"])
        self.assertEqual(60, config["rag"]["retrieval"]["rrf_k"])
        self.assertFalse(config["rag"]["retrieval"]["low_recall_query_expansion_enabled"])
        self.assertFalse(config["rag"]["retrieval"]["mmr_enabled"])
        self.assertEqual(0.92, config["rag"]["retrieval"]["duplicate_overlap_threshold"])
        self.assertEqual(50, config["rag"]["retrieval"]["direct_load_max_chunks"])
        self.assertEqual("default-workspace", config["rag"]["knowledge_base"]["default_workspace_id"])
        self.assertEqual("default-knowledge-base", config["rag"]["knowledge_base"]["default_knowledge_base_id"])


if __name__ == "__main__":
    unittest.main()
