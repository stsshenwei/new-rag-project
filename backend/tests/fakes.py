import tempfile
from pathlib import Path
from typing import Any


class FakeHybridMilvusStore:
    def __init__(self):
        self.persist_dir = Path(tempfile.mkdtemp())
        self.items: list[dict[str, Any]] = []
        self.upserted_chunks = []
        self.dense_hits: list[dict[str, Any]] = []
        self.bm25_hits: list[dict[str, Any]] = []

    def count(self):
        return len(self.items)

    def reset_collection(self):
        self.items.clear()
        self.upserted_chunks.clear()

    def upsert_chunks(self, chunks):
        self.upserted_chunks.extend(chunks)

    def query(self, question: str, top_k: int):
        return self.dense_hits[:top_k]

    def query_bm25(self, question: str, top_k: int):
        return self.bm25_hits[:top_k]


class FakeReranker:
    def __init__(self, scores: dict[str, float] | None = None, error: Exception | None = None):
        self.scores = scores or {}
        self.error = error

    def rerank(self, question: str, candidates: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        ranked = []
        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            chunk_id = str(metadata.get("chunk_id") or metadata.get("child_id") or candidate.get("content", ""))
            ranked.append({**candidate, "reranker_score": self.scores.get(chunk_id, 0.0)})
        ranked.sort(key=lambda item: item["reranker_score"], reverse=True)
        return ranked[:top_n]


class FakeOCRProvider:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = results or []
        self.error = error

    def extract(self, file_path):
        if self.error:
            raise self.error
        return self.results
