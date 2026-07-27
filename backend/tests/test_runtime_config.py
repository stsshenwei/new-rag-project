import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeCollection:
    def load(self):
        pass

    def num_entities(self):
        return 0


class RuntimeConfigTests(unittest.TestCase):
    def import_main_with_env(self, env: dict[str, str]):
        sys.modules.pop("app.main", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            full_env = {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "",
                "VECTOR_STORE_DIR": str(Path(tmpdir) / "vector_db"),
                "METADATA_DB_PATH": str(Path(tmpdir) / "metadata.sqlite3"),
                "RAG_DATA_DIR": str(Path(tmpdir) / "data"),
                "RERANKER_TOP_N": "8",
                "AGENTIC_RETRIEVAL_ENABLED": "false",
                "CHAT_AGENTIC_WORKFLOW_ENABLED": "false",
                "AGENT_TRACE_STREAM_ENABLED": "false",
                "RERANKER_ENABLED": "false",
                "RERANKER_PROVIDER": "local",
                "RERANKER_MODEL": "BAAI/bge-reranker-v2-m3",
                "RERANKER_TIMEOUT_SECONDS": "5.0",
                "OCR_ENABLED": "false",
                "OCR_PROVIDER": "docling",
                "KG_EXTRACTION_ENABLED": "false",
                **env,
            }
            with patch.dict(os.environ, full_env, clear=False):
                with patch("app.services.vector_store._create_or_load_collection", return_value=FakeCollection()):
                    module = importlib.import_module("app.main")
                    return module.build_rag_service()

    def test_runtime_config_defaults_are_disabled_safe(self):
        service = self.import_main_with_env({})

        self.assertFalse(service.milvus_bm25_enabled)
        self.assertFalse(service.vector_store.bm25_enabled)
        self.assertEqual(50, service.dense_recall_top_n)
        self.assertEqual(50, service.bm25_recall_top_n)
        self.assertEqual(30, service.fusion_top_k)
        self.assertEqual(60, service.rrf_k)
        self.assertEqual(0.7, service.rrf_vector_weight)
        self.assertEqual(0.3, service.rrf_keyword_weight)
        self.assertEqual(0.3, service.reranker_threshold)
        self.assertEqual(0.15, service.reranker_fallback_min_score)
        self.assertEqual(50, service.direct_load_max_chunks)
        self.assertEqual(240, service.context_short_chunk_min_chars)
        self.assertEqual(1200, service.context_expanded_chunk_max_chars)
        self.assertFalse(service.reranker_enabled)
        self.assertEqual("local", service.reranker_provider)
        self.assertEqual(8, service.reranker_top_n)
        self.assertEqual(5.0, service.reranker_timeout_seconds)
        self.assertFalse(service.low_recall_query_expansion_enabled)
        self.assertEqual(3, service.low_recall_min_candidates)
        self.assertEqual(0.2, service.low_recall_min_score)
        self.assertEqual(3, service.low_recall_max_queries)
        self.assertTrue(service.reranker_degradation_enabled)
        self.assertEqual(0.15, service.reranker_degraded_threshold)
        self.assertEqual(1, service.reranker_fallback_top_n)
        self.assertFalse(service.mmr_enabled)
        self.assertEqual(0.75, service.mmr_lambda)
        self.assertEqual(0, service.mmr_top_k)
        self.assertEqual(0.92, service.duplicate_overlap_threshold)
        self.assertFalse(service.ocr_enabled)
        self.assertEqual("docling", service.ocr_provider)
        self.assertTrue(service.query_understanding.config.enabled)
        self.assertFalse(service.query_understanding.config.rewrite_enabled)
        self.assertFalse(service.query_understanding.config.intent_detection_enabled)
        self.assertEqual(5, service.query_understanding.config.max_queries)
        self.assertFalse(service.kg_extraction_enabled)
        self.assertIsNone(service.kg_service)
        self.assertIsNone(service.graph_retriever)
        self.assertFalse(service.agentic_retrieval_enabled)
        self.assertIsNone(service.agentic_workflow)
        self.assertFalse(service.agent_trace_stream_enabled)
        self.assertFalse(service.chat_agentic_workflow_enabled)
        self.assertFalse(service.agent_runtime.config.web_search_enabled if service.agent_runtime else False)
        self.assertEqual("default-workspace", service.default_scope.workspace_id)
        self.assertEqual(("default-knowledge-base",), service.default_scope.selected_knowledge_base_ids)

    def test_runtime_config_reads_stable_default_knowledge_base_identity(self):
        service = self.import_main_with_env(
            {
                "DEFAULT_WORKSPACE_ID": "workspace-stable",
                "DEFAULT_WORKSPACE_NAME": "研发空间",
                "DEFAULT_KNOWLEDGE_BASE_ID": "kb-stable",
                "DEFAULT_KNOWLEDGE_BASE_NAME": "研发知识库",
            }
        )

        self.assertEqual("workspace-stable", service.default_scope.workspace_id)
        self.assertEqual(("kb-stable",), service.default_scope.selected_knowledge_base_ids)
        self.assertEqual("研发知识库", service.knowledge_base_service.repository.defaults.knowledge_base_name)

    def test_runtime_config_reads_enabled_values(self):
        service = self.import_main_with_env(
            {
                "MILVUS_BM25_ENABLED": "true",
                "DENSE_RECALL_TOP_N": "11",
                "BM25_RECALL_TOP_N": "13",
                "FUSION_TOP_K": "17",
                "RRF_K": "44",
                "RRF_VECTOR_WEIGHT": "0.8",
                "RRF_KEYWORD_WEIGHT": "0.2",
                "RERANKER_THRESHOLD": "0.45",
                "RERANKER_FALLBACK_MIN_SCORE": "0.25",
                "DIRECT_LOAD_MAX_CHUNKS": "12",
                "CONTEXT_SHORT_CHUNK_MIN_CHARS": "180",
                "CONTEXT_EXPANDED_CHUNK_MAX_CHARS": "900",
                "RERANKER_ENABLED": "true",
                "RERANKER_PROVIDER": "local",
                "RERANKER_TOP_N": "7",
                "RERANKER_TIMEOUT_SECONDS": "2.5",
                "LOW_RECALL_QUERY_EXPANSION_ENABLED": "true",
                "LOW_RECALL_MIN_CANDIDATES": "4",
                "LOW_RECALL_MIN_SCORE": "0.22",
                "LOW_RECALL_MAX_QUERIES": "2",
                "RERANKER_DEGRADATION_ENABLED": "false",
                "RERANKER_DEGRADED_THRESHOLD": "0.12",
                "RERANKER_FALLBACK_TOP_N": "3",
                "MMR_ENABLED": "true",
                "MMR_LAMBDA": "0.62",
                "MMR_TOP_K": "6",
                "DUPLICATE_OVERLAP_THRESHOLD": "0.88",
                "OCR_ENABLED": "true",
                "OCR_PROVIDER": "docling",
                "QUERY_UNDERSTANDING_ENABLED": "false",
                "QUERY_REWRITE_ENABLED": "true",
                "QUERY_INTENT_DETECTION_ENABLED": "true",
                "QUERY_REWRITE_MAX_QUERIES": "9",
                "KG_EXTRACTION_ENABLED": "true",
            }
        )

        self.assertTrue(service.milvus_bm25_enabled)
        self.assertTrue(service.vector_store.bm25_enabled)
        self.assertEqual(11, service.dense_recall_top_n)
        self.assertEqual(13, service.bm25_recall_top_n)
        self.assertEqual(17, service.fusion_top_k)
        self.assertEqual(44, service.rrf_k)
        self.assertEqual(0.8, service.rrf_vector_weight)
        self.assertEqual(0.2, service.rrf_keyword_weight)
        self.assertEqual(0.45, service.reranker_threshold)
        self.assertEqual(0.25, service.reranker_fallback_min_score)
        self.assertEqual(12, service.direct_load_max_chunks)
        self.assertEqual(180, service.context_short_chunk_min_chars)
        self.assertEqual(900, service.context_expanded_chunk_max_chars)
        self.assertTrue(service.reranker_enabled)
        self.assertEqual("local", service.reranker_provider)
        self.assertEqual(7, service.reranker_top_n)
        self.assertEqual(2.5, service.reranker_timeout_seconds)
        self.assertTrue(service.low_recall_query_expansion_enabled)
        self.assertEqual(4, service.low_recall_min_candidates)
        self.assertEqual(0.22, service.low_recall_min_score)
        self.assertEqual(2, service.low_recall_max_queries)
        self.assertFalse(service.reranker_degradation_enabled)
        self.assertEqual(0.12, service.reranker_degraded_threshold)
        self.assertEqual(3, service.reranker_fallback_top_n)
        self.assertTrue(service.mmr_enabled)
        self.assertEqual(0.62, service.mmr_lambda)
        self.assertEqual(6, service.mmr_top_k)
        self.assertEqual(0.88, service.duplicate_overlap_threshold)
        self.assertTrue(service.ocr_enabled)
        self.assertEqual("docling", service.ocr_provider)
        self.assertFalse(service.query_understanding.config.enabled)
        self.assertTrue(service.query_understanding.config.rewrite_enabled)
        self.assertTrue(service.query_understanding.config.intent_detection_enabled)
        self.assertEqual(9, service.query_understanding.config.max_queries)
        self.assertTrue(service.kg_extraction_enabled)
        self.assertIsNotNone(service.kg_service)

    def test_runtime_config_reads_agentic_retrieval_values(self):
        service = self.import_main_with_env(
            {
                "AGENTIC_RETRIEVAL_ENABLED": "true",
                "AGENT_TRACE_STREAM_ENABLED": "true",
                "AGENTIC_MAX_TOOL_CALLS": "4",
                "AGENTIC_TOOL_TIMEOUT_SECONDS": "3.5",
                "AGENTIC_RAW_TOP_K": "5",
                "AGENTIC_KEYWORD_TOP_K": "6",
                "AGENTIC_GRAPH_TOP_K": "7",
                "AGENTIC_GRAPH_MAX_DEPTH": "2",
            }
        )

        self.assertTrue(service.agentic_retrieval_enabled)
        self.assertTrue(service.agent_trace_stream_enabled)
        self.assertIsNotNone(service.agentic_workflow)
        self.assertEqual(4, service.agentic_workflow.config.max_tool_calls)
        self.assertEqual(3.5, service.agentic_workflow.config.tool_timeout_seconds)
        self.assertEqual(5, service.agentic_workflow.config.raw_top_k)
        self.assertEqual(6, service.agentic_workflow.config.keyword_top_k)
        self.assertEqual(7, service.agentic_workflow.config.graph_top_k)
        self.assertEqual(2, service.agentic_workflow.config.graph_max_depth)

    def test_runtime_config_reads_extended_agent_runtime_tool_values(self):
        service = self.import_main_with_env(
            {
                "AGENT_RUNTIME_ENABLED": "true",
                "AGENT_RUNTIME_ENABLED_TOOLS": "web_search,web_fetch,data_analysis,database_query,execute_skill",
                "AGENT_RUNTIME_WEB_SEARCH_ENABLED": "true",
                "AGENT_RUNTIME_WEB_SEARCH_URL": "https://search.example.com/api",
                "AGENT_RUNTIME_WEB_FETCH_ENABLED": "true",
                "AGENT_RUNTIME_WEB_FETCH_ALLOWED_DOMAINS": "example.com,docs.example.com",
                "AGENT_RUNTIME_DATA_ANALYSIS_ENABLED": "true",
                "AGENT_RUNTIME_DATABASE_QUERY_ENABLED": "true",
                "AGENT_RUNTIME_DATABASE_SOURCES": "main=./vector_db/rag_metadata.sqlite3",
            }
        )

        self.assertIsNotNone(service.agent_runtime)
        self.assertTrue(service.agent_runtime.config.web_search_enabled)
        self.assertEqual("https://search.example.com/api", service.agent_runtime.config.web_search_endpoint)
        self.assertTrue(service.agent_runtime.config.web_fetch_enabled)
        self.assertEqual(("example.com", "docs.example.com"), service.agent_runtime.config.web_fetch_allowed_domains)
        self.assertTrue(service.agent_runtime.config.data_analysis_enabled)
        self.assertTrue(service.agent_runtime.config.database_query_enabled)
        self.assertEqual({"main": "./vector_db/rag_metadata.sqlite3"}, service.agent_runtime.config.database_allowed_sources)
        self.assertEqual(
            ["data_analysis", "database_query", "execute_skill", "web_fetch", "web_search"],
            service.agent_runtime.tool_registry.list_tools(),
        )

    def test_runtime_config_reads_unified_quick_runtime_policy_values(self):
        service = self.import_main_with_env(
            {
                "AGENT_RUNTIME_ENABLED": "false",
                "CHAT_UNIFIED_RUNTIME_ENABLED": "true",
                "AGENT_RUNTIME_QUICK_PROMPT_TEMPLATE_ID": "quick_rag_agent",
                "AGENT_RUNTIME_QUICK_CONTEXT_TEMPLATE_ID": "qa_context",
                "AGENT_RUNTIME_QUICK_ENABLED_TOOLS": "thinking",
                "AGENT_RUNTIME_QUICK_MAX_ITERATIONS": "2",
                "AGENT_RUNTIME_QUICK_MAX_EMPTY_RETRIES": "1",
                "AGENT_RUNTIME_QUICK_MAX_REPEATED_RESPONSES": "1",
                "AGENT_RUNTIME_QUICK_PRELOAD_RETRIEVAL": "true",
                "AGENT_RUNTIME_QUICK_REMEDIAL_RETRIEVAL_ENABLED": "false",
            }
        )

        self.assertFalse(service.agent_runtime_enabled)
        self.assertTrue(service.unified_chat_runtime_enabled)
        self.assertTrue(service.quick_runtime_enabled)
        self.assertIsNotNone(service.agent_runtime)
        config = service.agent_runtime.config
        self.assertEqual("quick_rag_agent", config.quick_prompt_template_id)
        self.assertEqual("qa_context", config.quick_context_template_id)
        self.assertEqual(("thinking",), config.quick_enabled_tools)
        self.assertEqual(2, config.quick_max_iterations)
        self.assertEqual(1, config.quick_max_empty_retries)

    def test_runtime_config_keeps_startup_safe_when_neo4j_driver_missing(self):
        service = self.import_main_with_env(
            {
                "KG_EXTRACTION_ENABLED": "true",
                "KG_GRAPH_ENABLED": "true",
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password",
            }
        )

        self.assertTrue(service.kg_extraction_enabled)
        self.assertIsNotNone(service.kg_service)
        self.assertIsNotNone(service.kg_service.graph_store)

    def test_runtime_config_keeps_graph_retriever_optional_when_neo4j_driver_missing(self):
        service = self.import_main_with_env(
            {
                "GRAPH_RETRIEVER_ENABLED": "true",
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password",
            }
        )

        self.assertIsNone(service.graph_retriever)

    def test_runtime_config_loads_query_terms_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            terms_path = Path(tmpdir) / "terms.yaml"
            terms_path.write_text(
                """
terms:
  电口:
    canonical: RJ-45
    aliases:
      - RJ45
""",
                encoding="utf-8",
            )

            service = self.import_main_with_env({"QUERY_TERMS_PATH": str(terms_path)})

        result = service.query_understanding.understand("8个电口")

        self.assertIn("RJ-45", result.expanded_terms)

    def test_runtime_config_reads_yaml_defaults_when_env_absent(self):
        sys.modules.pop("app.main", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "rag.yaml"
            config_path.write_text(
                """
rag:
  embedding:
    model: yaml-embedding
  vector_store:
    type: milvus
    url: http://127.0.0.1:19530
    collection: yaml_chunks
  keyword_search:
    type: milvus
  reranker:
    provider: bge
    model: yaml-reranker
  retrieval:
    dense_top_k: 21
    keyword_top_k: 22
    fusion_top_k: 23
    rerank_top_k: 6
    rrf_k: 45
    rrf_vector_weight: 0.6
    rrf_keyword_weight: 0.4
    reranker_threshold: 0.55
    reranker_fallback_min_score: 0.22
    direct_load_max_chunks: 14
  context:
    short_chunk_min_chars: 190
    expanded_chunk_max_chars: 950
  llm:
    model: yaml-chat
""",
                encoding="utf-8",
            )
            env = {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "",
                "VECTOR_STORE_DIR": str(Path(tmpdir) / "vector_db"),
                "METADATA_DB_PATH": str(Path(tmpdir) / "metadata.sqlite3"),
                "RAG_DATA_DIR": str(Path(tmpdir) / "data"),
                "RAG_CONFIG_PATH": str(config_path),
                "AUTO_INGEST_ON_STARTUP": "false",
                "RERANKER_TOP_N": "",
                "RERANKER_PROVIDER": "",
                "RERANKER_MODEL": "",
                "OPENAI_EMBEDDING_MODEL": "",
                "OPENAI_CHAT_MODEL": "",
                "MILVUS_COLLECTION": "",
                "DENSE_RECALL_TOP_N": "",
                "BM25_RECALL_TOP_N": "",
                "FUSION_TOP_K": "",
                "RRF_K": "",
                "RRF_VECTOR_WEIGHT": "",
                "RRF_KEYWORD_WEIGHT": "",
                "RERANKER_THRESHOLD": "",
                "RERANKER_FALLBACK_MIN_SCORE": "",
                "DIRECT_LOAD_MAX_CHUNKS": "",
                "CONTEXT_SHORT_CHUNK_MIN_CHARS": "",
                "CONTEXT_EXPANDED_CHUNK_MAX_CHARS": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("app.services.vector_store._create_or_load_collection", return_value=FakeCollection()):
                    module = importlib.import_module("app.main")
                    service = module.build_rag_service()

        self.assertEqual("yaml-chat", service.chat_model)
        self.assertEqual("yaml_chunks", service.vector_store.collection_name)
        self.assertEqual(21, service.dense_recall_top_n)
        self.assertEqual(22, service.bm25_recall_top_n)
        self.assertEqual(23, service.fusion_top_k)
        self.assertEqual(6, service.reranker_top_n)
        self.assertEqual(45, service.rrf_k)
        self.assertEqual(0.6, service.rrf_vector_weight)
        self.assertEqual(0.4, service.rrf_keyword_weight)
        self.assertEqual(0.55, service.reranker_threshold)
        self.assertEqual(0.22, service.reranker_fallback_min_score)
        self.assertEqual(14, service.direct_load_max_chunks)
        self.assertEqual(190, service.context_short_chunk_min_chars)
        self.assertEqual(950, service.context_expanded_chunk_max_chars)
        self.assertEqual("bge", service.reranker_provider)

    def test_app_health_starts_with_optional_services_disabled(self):
        sys.modules.pop("app.main", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "",
                "VECTOR_STORE_DIR": str(Path(tmpdir) / "vector_db"),
                "METADATA_DB_PATH": str(Path(tmpdir) / "metadata.sqlite3"),
                "RAG_DATA_DIR": str(Path(tmpdir) / "data"),
                "AUTO_INGEST_ON_STARTUP": "false",
                "MILVUS_BM25_ENABLED": "false",
                "RERANKER_ENABLED": "false",
                "OCR_ENABLED": "false",
                "KG_EXTRACTION_ENABLED": "false",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("app.services.vector_store._create_or_load_collection", return_value=FakeCollection()):
                    module = importlib.import_module("app.main")
                    from fastapi.testclient import TestClient

                    with TestClient(module.app) as client:
                        response = client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True}, response.json())


if __name__ == "__main__":
    unittest.main()
