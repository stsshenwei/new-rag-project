from typing import Any

from app.services.retrieval_models import RetrievedChunk


class HybridRetriever:
    def __init__(
        self,
        embedding_provider: Any,
        dense_search: Any,
        keyword_search: Any,
        dense_top_k: int = 50,
        keyword_top_k: int = 50,
        fusion_top_k: int = 30,
        fusion_strategy: str = "rrf",
        rrf_k: int = 60,
        dense_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        self.embedding_provider = embedding_provider
        self.dense_search = dense_search
        self.keyword_search = keyword_search
        self.dense_top_k = dense_top_k
        self.keyword_top_k = keyword_top_k
        self.fusion_top_k = fusion_top_k
        self.fusion_strategy = fusion_strategy
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.keyword_weight = keyword_weight

    def retrieve(self, question: str, top_k: int | None = None, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        query_embedding = self.embedding_provider.embed_text(question)
        dense_results = self.dense_search.search(query_embedding, self.dense_top_k, filters)
        keyword_results = self.keyword_search.search(question, self.keyword_top_k, filters)
        limit = top_k or self.fusion_top_k
        return self._fuse(dense_results, keyword_results)[:limit]

    def _fuse(self, dense_results: list[RetrievedChunk], keyword_results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        merged: dict[str, RetrievedChunk] = {}
        scores: dict[str, dict[str, float]] = {}

        for rank, chunk in enumerate(dense_results, start=1):
            merged.setdefault(chunk.chunk_id, chunk)
            scores.setdefault(chunk.chunk_id, {"dense": 0.0, "keyword": 0.0, "hybrid": 0.0})
            scores[chunk.chunk_id]["dense"] = max(scores[chunk.chunk_id]["dense"], chunk.score)
            scores[chunk.chunk_id]["hybrid"] += self._rank_score(rank, chunk.score, self.dense_weight)

        for rank, chunk in enumerate(keyword_results, start=1):
            merged.setdefault(chunk.chunk_id, chunk)
            scores.setdefault(chunk.chunk_id, {"dense": 0.0, "keyword": 0.0, "hybrid": 0.0})
            scores[chunk.chunk_id]["keyword"] = max(scores[chunk.chunk_id]["keyword"], chunk.score)
            scores[chunk.chunk_id]["hybrid"] += self._rank_score(rank, chunk.score, self.keyword_weight)

        fused = []
        for chunk_id, chunk in merged.items():
            score_data = scores[chunk_id]
            fused.append(
                RetrievedChunk(
                    **{
                        **chunk.__dict__,
                        "score": score_data["hybrid"],
                        "vector_score": score_data["dense"] or chunk.vector_score,
                        "bm25_score": score_data["keyword"] or chunk.bm25_score,
                        "hybrid_score": score_data["hybrid"],
                    }
                )
            )
        fused.sort(key=lambda item: item.hybrid_score or 0.0, reverse=True)
        return fused

    def _rank_score(self, rank: int, raw_score: float, weight: float) -> float:
        if self.fusion_strategy == "weighted":
            return raw_score * weight
        return 1.0 / (self.rrf_k + rank)
