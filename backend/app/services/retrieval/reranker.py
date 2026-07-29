import logging
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from app.services.infrastructure.observability import get_observability_sink

logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"


class NoOpReranker:
    def rerank(self, question: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        logger.debug("provider.reranker.noop", extra={"provider": "noop", "items": len(chunks), "top_k": top_k})
        return chunks[:top_k]


class LocalCrossEncoderReranker:
    def __init__(self, model: str):
        try:
            from sentence_transformers import CrossEncoder
        except Exception as exc:
            raise RuntimeError("Local reranker requires sentence-transformers to be installed.") from exc
        self.model_name = model
        self._model = CrossEncoder(model)

    def rerank(self, question: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        started = time.monotonic()
        logger.debug("provider.reranker.start", extra={"provider": "local", "model": self.model_name, "items": len(chunks), "top_k": top_k})
        pairs = [(question, str(chunk.get("content", ""))) for chunk in chunks]
        generation = get_observability_sink().start_generation(
            name="rerank",
            model=self.model_name,
            input=_rerank_input(question, chunks, top_k),
            metadata={"provider": "local", "candidate_count": len(chunks), "top_k": top_k},
        )
        try:
            scores = self._model.predict(pairs)
            ranked = []
            for chunk, score in zip(chunks, scores, strict=False):
                ranked.append({**chunk, "reranker_score": float(score)})
            ranked.sort(key=lambda item: item["reranker_score"], reverse=True)
            result = ranked[:top_k]
            generation.finish(output=_rerank_output(result, len(ranked)), usage=_rerank_usage(question, chunks))
            logger.debug(
                "provider.reranker.end",
                extra={"provider": "local", "model": self.model_name, "items": len(chunks), "returned": len(result), "duration_ms": int((time.monotonic() - started) * 1000)},
            )
            return result
        except Exception as exc:
            generation.finish(error=exc)
            logger.exception(
                "provider.reranker.failed",
                extra={"provider": "local", "model": self.model_name, "items": len(chunks), "error_type": exc.__class__.__name__},
            )
            raise


class DashScopeReranker:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = DEFAULT_DASHSCOPE_RERANK_URL,
        timeout_seconds: float = 10.0,
    ):
        if not api_key:
            raise RuntimeError("DashScope reranker requires RERANKER_API_KEY or DASHSCOPE_API_KEY.")
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def rerank(self, question: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        started = time.monotonic()
        logger.debug("provider.reranker.start", extra={"provider": "dashscope", "model": self.model_name, "items": len(chunks), "top_k": top_k})
        generation = get_observability_sink().start_generation(
            name="rerank",
            model=self.model_name,
            input=_rerank_input(question, chunks, top_k),
            metadata={"provider": "dashscope", "candidate_count": len(chunks), "top_k": top_k},
        )
        candidates = chunks[:]
        if not candidates:
            generation.finish(output={"count": 0}, usage={})
            return []
        valid_candidates = [
            (index, chunk, str(chunk.get("content", "")).strip())
            for index, chunk in enumerate(candidates)
            if str(chunk.get("content", "")).strip()
        ]
        if not valid_candidates:
            logger.warning("DashScope reranker skipped because every candidate document is empty")
            generation.finish(output={"count": len(candidates), "skipped": "empty_documents"}, usage={})
            return candidates[:top_k]
        documents = [content for _, _, content in valid_candidates]
        payload = {
            "model": self.model_name,
            "input": {
                "query": question,
                "documents": documents,
            },
            "parameters": {
                "top_n": min(top_k, len(documents)),
                "return_documents": False,
            },
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            generation.finish(error=exc)
            logger.exception(
                "provider.reranker.failed",
                extra={"provider": "dashscope", "model": self.model_name, "items": len(chunks), "error_type": exc.__class__.__name__},
            )
            raise RuntimeError(f"DashScope reranker HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            generation.finish(error=exc)
            logger.exception(
                "provider.reranker.failed",
                extra={"provider": "dashscope", "model": self.model_name, "items": len(chunks), "error_type": exc.__class__.__name__},
            )
            raise RuntimeError(f"DashScope reranker request failed: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except Exception as exc:
            generation.finish(error=exc)
            logger.exception(
                "provider.reranker.failed",
                extra={"provider": "dashscope", "model": self.model_name, "items": len(chunks), "error_type": exc.__class__.__name__},
            )
            raise
        results = parsed.get("output", {}).get("results", [])
        ranked: list[dict[str, Any]] = []
        used_indexes: set[int] = set()
        for item in results:
            index = item.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(valid_candidates):
                continue
            original_index, candidate, _ = valid_candidates[index]
            used_indexes.add(original_index)
            score = item.get("relevance_score", item.get("score", 0.0))
            ranked.append({**candidate, "reranker_score": float(score)})
        if len(ranked) < min(top_k, len(candidates)):
            for index, chunk in enumerate(candidates):
                if index in used_indexes:
                    continue
                ranked.append({**chunk, "reranker_score": float(chunk.get("hybrid_score", chunk.get("vector_score", 0.0)))})
                if len(ranked) >= top_k:
                    break
        ranked.sort(key=lambda item: item["reranker_score"], reverse=True)
        result = ranked[:top_k]
        generation.finish(output=_rerank_output(result, len(ranked)), usage=_rerank_usage(question, chunks))
        logger.debug(
            "provider.reranker.end",
            extra={"provider": "dashscope", "model": self.model_name, "items": len(chunks), "returned": len(result), "duration_ms": int((time.monotonic() - started) * 1000)},
        )
        return result


def build_reranker(
    enabled: bool,
    provider: str = "local",
    model: str = "BAAI/bge-reranker-v2-m3",
    api_key: str | None = None,
    base_url: str = DEFAULT_DASHSCOPE_RERANK_URL,
    timeout_seconds: float = 10.0,
) -> Any:
    if not enabled:
        return NoOpReranker()
    normalized = provider.strip().lower()
    if normalized in {"local", "bge"}:
        try:
            return LocalCrossEncoderReranker(model)
        except RuntimeError as exc:
            logger.warning("Local reranker unavailable, falling back to no-op reranker: %s", exc)
            return NoOpReranker()
    if normalized in {"dashscope", "qwen", "aliyun"}:
        try:
            return DashScopeReranker(
                model=model,
                api_key=api_key or os.getenv("RERANKER_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or "",
                base_url=base_url or DEFAULT_DASHSCOPE_RERANK_URL,
                timeout_seconds=timeout_seconds,
            )
        except RuntimeError as exc:
            logger.warning("DashScope reranker unavailable, falling back to no-op reranker: %s", exc)
            return NoOpReranker()
    logger.warning("Unsupported reranker provider %r, falling back to no-op reranker.", provider)
    return NoOpReranker()


def _rerank_input(question: str, chunks: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    previews = []
    for index, chunk in enumerate(chunks[:8]):
        metadata = chunk.get("metadata") or {}
        previews.append(
            {
                "index": index,
                "chunk_id": metadata.get("chunk_id") or metadata.get("child_id") or chunk.get("id") or "",
                "doc_id": metadata.get("doc_id") or "",
                "preview": str(chunk.get("content") or "")[:160],
            }
        )
    return {"query": question, "candidate_count": len(chunks), "top_k": top_k, "candidates_preview": previews}


def _rerank_output(result: list[dict[str, Any]], total_count: int) -> dict[str, Any]:
    scores = [float(item.get("reranker_score", 0.0)) for item in result]
    return {
        "returned": len(result),
        "total_ranked": total_count,
        "top_hits": [
            {
                "rank": index + 1,
                "score": float(item.get("reranker_score", 0.0)),
                "chunk_id": (item.get("metadata") or {}).get("chunk_id") or (item.get("metadata") or {}).get("child_id") or "",
            }
            for index, item in enumerate(result[:20])
        ],
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
    }


def _rerank_usage(question: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = (len(question) // 4) + 1
    tokens += sum((len(str(chunk.get("content") or "")) // 4) + 1 for chunk in chunks)
    return {"input": tokens, "total": tokens, "unit": "TOKENS"} if tokens else {}
