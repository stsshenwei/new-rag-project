from typing import Any

from app.services.document_chunker import estimate_tokens
from app.services.retrieval_models import BuiltContext, RetrievedChunk


class ContextBuilder:
    def __init__(self, repository: Any, max_tokens: int = 8000, include_neighbor_chunks: bool = True):
        self.repository = repository
        self.max_tokens = max_tokens
        self.include_neighbor_chunks = include_neighbor_chunks

    def build(self, question: str, reranked_chunks: list[RetrievedChunk]) -> BuiltContext:
        selected: dict[str, dict[str, Any]] = {}
        for chunk in reranked_chunks:
            parent_id = chunk.parent_id or chunk.chunk_id
            parent = self.repository.get_chunk(parent_id) if parent_id else None
            if parent is None:
                continue
            current = selected.setdefault(parent_id, self._parent_context(parent, chunk))
            current["matched_children"].append(self._child_ref(chunk))
            if self.include_neighbor_chunks:
                current.setdefault("neighbor_chunk_ids", []).extend(self._neighbor_chunk_ids(chunk))
            current["score"] = max(float(current.get("score", 0.0)), float(chunk.reranker_score or chunk.hybrid_score or chunk.score))

        ordered = sorted(selected.values(), key=lambda item: item["score"], reverse=True)
        kept: list[dict[str, Any]] = []
        total_tokens = 0
        for item in ordered:
            token_count = estimate_tokens(item["content"])
            if kept and total_tokens + token_count > self.max_tokens:
                continue
            kept.append(item)
            total_tokens += token_count

        text = "\n\n".join(self._format_parent(idx, item) for idx, item in enumerate(kept, start=1))
        return BuiltContext(question=question, text=text, selected_parent_chunks=kept, token_count=total_tokens)

    def _parent_context(self, parent: dict[str, Any], first_child: RetrievedChunk) -> dict[str, Any]:
        metadata = parent.get("metadata_json", {})
        return {
            "doc_id": parent.get("doc_id", first_child.doc_id),
            "parent_id": parent.get("id", first_child.parent_id),
            "file_name": metadata.get("file_name", metadata.get("source", "")),
            "title_path": parent.get("title_path", first_child.title_path),
            "page_start": parent.get("page_start", first_child.page_start),
            "page_end": parent.get("page_end", first_child.page_end),
            "content": metadata.get("llm_context") or parent.get("content_markdown") or parent.get("content", ""),
            "matched_children": [],
            "neighbor_chunk_ids": [],
            "score": float(first_child.reranker_score or first_child.hybrid_score or first_child.score),
        }

    def _neighbor_chunk_ids(self, child: RetrievedChunk) -> list[str]:
        list_chunks = getattr(self.repository, "list_chunks", None)
        if not callable(list_chunks):
            return []
        siblings = list_chunks(doc_id=child.doc_id, chunk_types={"child", "table", "ocr"})
        ids = [str(item.get("id", "")) for item in siblings]
        try:
            idx = ids.index(child.chunk_id)
        except ValueError:
            return []
        neighbors = []
        for pos in [idx - 1, idx + 1]:
            if 0 <= pos < len(ids):
                neighbors.append(ids[pos])
        return neighbors

    def _child_ref(self, child: RetrievedChunk) -> dict[str, Any]:
        return {
            "chunk_id": child.chunk_id,
            "summary": child.content[:240],
            "score": float(child.reranker_score or child.hybrid_score or child.score),
        }

    def _format_parent(self, index: int, item: dict[str, Any]) -> str:
        header = (
            f"[{index}] file={item.get('file_name', '')} title_path={item.get('title_path', '')} "
            f"pages={item.get('page_start')}-{item.get('page_end')}"
        )
        child_summaries = "\n".join(f"- hit {child['chunk_id']}: {child['summary']}" for child in item["matched_children"])
        return f"{header}\n{item['content']}\nMatched children:\n{child_summaries}".strip()
