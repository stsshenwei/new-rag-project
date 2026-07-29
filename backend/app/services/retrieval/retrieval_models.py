from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    parent_id: str
    content: str = ""
    chunk_type: str = "child"
    title_path: str = ""
    page_start: int | None = None
    page_end: int | None = None
    score: float = 0.0
    vector_score: float | None = None
    bm25_score: float | None = None
    hybrid_score: float | None = None
    reranker_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuiltContext:
    question: str
    text: str
    selected_parent_chunks: list[dict[str, Any]]
    token_count: int


@dataclass(frozen=True)
class Citation:
    doc_id: str
    file_name: str
    chunk_id: str
    parent_id: str
    title_path: str
    page_start: int | None = None
    page_end: int | None = None
    quote: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class Answer:
    answer: str
    citations: list[Citation]
    used_chunks: list[str]
    confidence: float
    debug_info: dict[str, Any] | None = None


class KeywordSearch(Protocol):
    def index(self, chunks: list[Any]) -> None:
        ...

    def search(self, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        ...

    def delete_by_doc_id(self, doc_id: str) -> None:
        ...


class VectorIndexProvider(Protocol):
    def reset_collection(self) -> None:
        ...

    def upsert_chunks(self, chunks: list[Any]) -> None:
        ...

    def replace_document_chunks(self, doc_id: str, chunks: list[Any]) -> None:
        ...

    def delete_document(self, doc_id: str) -> None:
        ...

    def query_dense(self, question: str, top_k: int) -> list[dict[str, Any]]:
        ...

    def query_bm25(self, question: str, top_k: int) -> list[dict[str, Any]]:
        ...


class EvidenceRepository(Protocol):
    def replace_chunks(self, doc_id: str, chunks: list[Any]) -> None:
        ...

    def reset(self) -> None:
        ...

    def delete_document(self, doc_id: str) -> None:
        ...

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        ...

    def search_keyword_chunks(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...


class HybridRetriever(Protocol):
    def retrieve(self, question: str, top_k: int, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        ...


class Reranker(Protocol):
    def rerank(self, question: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        ...


class ContextBuilder(Protocol):
    def build(self, question: str, reranked_chunks: list[RetrievedChunk]) -> BuiltContext:
        ...


class LLMProvider(Protocol):
    def generate_answer(self, question: str, context: BuiltContext) -> Answer:
        ...
