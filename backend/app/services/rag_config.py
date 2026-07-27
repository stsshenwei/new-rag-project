import os
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_RAG_CONFIG: dict[str, Any] = {
    "rag": {
        "knowledge_base": {
            "default_workspace_id": "default-workspace",
            "default_workspace_name": "默认工作空间",
            "default_knowledge_base_id": "default-knowledge-base",
            "default_knowledge_base_name": "默认知识库",
        },
        "parser": {"type": "docling"},
        "embedding": {"provider": "openai", "model": "text-embedding-3-small", "base_url": "${OPENAI_BASE_URL}", "api_key": "${OPENAI_API_KEY}"},
        "vector_store": {"type": "milvus", "url": "${MILVUS_URI}", "collection": "rag_chunk_vectors"},
        "keyword_search": {"type": "milvus", "url": "${MILVUS_URI}", "index": "rag_chunk_vectors"},
        "reranker": {"enabled": False, "provider": "local", "model": "BAAI/bge-reranker-v2-m3"},
        "retrieval": {
            "dense_top_k": 50,
            "keyword_top_k": 50,
            "fusion_top_k": 30,
            "rerank_top_k": 8,
            "rrf_k": 60,
            "rrf_vector_weight": 0.7,
            "rrf_keyword_weight": 0.3,
            "reranker_threshold": 0.3,
            "reranker_fallback_min_score": 0.15,
            "reranker_degradation_enabled": True,
            "reranker_degraded_threshold": 0.15,
            "reranker_fallback_top_n": 1,
            "low_recall_query_expansion_enabled": False,
            "low_recall_min_candidates": 3,
            "low_recall_min_score": 0.2,
            "low_recall_max_queries": 3,
            "mmr_enabled": False,
            "mmr_lambda": 0.75,
            "mmr_top_k": 0,
            "duplicate_overlap_threshold": 0.92,
            "direct_load_max_chunks": 50,
        },
        "context": {
            "max_tokens": 8000,
            "include_neighbor_chunks": True,
            "short_chunk_min_chars": 240,
            "expanded_chunk_max_chars": 1200,
        },
        "processing_worker": {
            "enabled": False,
            "poll_interval_seconds": 1.0,
            "lease_timeout_seconds": 300,
            "max_concurrent_tasks": 1,
            "default_max_attempts": 3,
            "retry_backoff_seconds": [10, 30, 120],
            "parser_max_attempts": 3,
            "chunk_max_attempts": 2,
            "embedding_max_attempts": 3,
            "multimodal_max_attempts": 3,
            "postprocess_max_attempts": 2,
        },
        "llm": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "${OPENAI_BASE_URL}", "api_key": "${OPENAI_API_KEY}"},
    }
}


def load_rag_config(path: str | Path | None = None) -> dict[str, Any]:
    config = _deep_merge({}, DEFAULT_RAG_CONFIG)
    if path:
        raw = Path(path).read_text(encoding="utf-8")
        loaded = yaml.safe_load(_resolve_env(raw)) or {}
        config = _deep_merge(config, loaded)
    else:
        config = _resolve_env_values(config)
    return config


def _resolve_env(raw: str) -> str:
    pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")
    return pattern.sub(lambda match: os.getenv(match.group(1), ""), raw)


def _resolve_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_values(item) for item in value]
    if isinstance(value, str):
        return _resolve_env(value)
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
