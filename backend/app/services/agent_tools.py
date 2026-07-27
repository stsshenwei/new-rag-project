from __future__ import annotations

import inspect
from typing import Any, Protocol

from app.models.agentic_retrieval import (
    TOOL_GRAPH_RETRIEVER,
    TOOL_KEYWORD_SEARCH,
    TOOL_RAW_RAG,
    EvidenceBundle,
    EvidenceItem,
    PlannedTool,
    ToolResult,
)
from app.models.knowledge_base import KnowledgeBaseScope


class RetrievalTool(Protocol):
    name: str

    def run(self, question: str, planned_tool: PlannedTool, scope: KnowledgeBaseScope | None = None) -> ToolResult:
        ...


class RawRAGTool:
    name = TOOL_RAW_RAG

    def __init__(self, rag_service):
        self.rag_service = rag_service

    def run(self, question: str, planned_tool: PlannedTool, scope: KnowledgeBaseScope | None = None) -> ToolResult:
        try:
            child_hits = _call_scoped(self.rag_service, "hybrid_retrieve_hits", question, scope=scope)
            hits = _call_scoped(self.rag_service, "recall_parent_hits", child_hits, scope=scope)
            constraint_filter = getattr(self.rag_service, "filter_hits_for_question_constraints", None)
            if callable(constraint_filter):
                hits = constraint_filter(question, hits)
            citations = self.rag_service.extract_sources(hits)
            items = [_hit_to_evidence_item(hit, self.name, index) for index, hit in enumerate(hits)]
            used_chunks = _used_chunks_from_hits(hits)
            source_chunk_ids = list(dict.fromkeys([*used_chunks, *[item.chunk_id for item in items if item.chunk_id]]))
            bundle = EvidenceBundle(
                items=items,
                citations=citations,
                used_chunks=used_chunks,
                source_chunk_ids=source_chunk_ids,
                confidence=_max_hit_score(hits),
                metadata={
                    "raw_hits": hits,
                    "result_count": len(items),
                    "doc_count": len(_evidence_source_titles(items, citations)),
                    "used_chunks": len(source_chunk_ids),
                },
            )
            return ToolResult(self.name, planned_tool.action, "completed", bundle, observation=f"{len(items)} raw chunks")
        except Exception as exc:
            return ToolResult(self.name, planned_tool.action, "failed", EvidenceBundle(), error=str(exc), observation="Raw RAG failed")


class KeywordSearchTool:
    name = TOOL_KEYWORD_SEARCH

    def __init__(self, rag_service):
        self.rag_service = rag_service

    def run(self, question: str, planned_tool: PlannedTool, scope: KnowledgeBaseScope | None = None) -> ToolResult:
        try:
            hits = _call_scoped(
                self.rag_service,
                "keyword_retrieve_hits",
                question,
                top_k=planned_tool.limits.get("top_k"),
                scope=scope,
            )
            items = [_hit_to_evidence_item(hit, self.name, index) for index, hit in enumerate(hits)]
            source_chunk_ids = list(dict.fromkeys([item.chunk_id for item in items if item.chunk_id]))
            bundle = EvidenceBundle(
                items=items,
                used_chunks=source_chunk_ids,
                source_chunk_ids=source_chunk_ids,
                confidence=_max_hit_score(hits),
                metadata={
                    "keyword_hits": hits,
                    "result_count": len(items),
                    "matched_chunks": len(items),
                    "total_matches": len(items),
                    "doc_count": len(_evidence_source_titles(items)),
                    "query": question,
                },
            )
            return ToolResult(self.name, planned_tool.action, "completed", bundle, observation=f"{len(items)} keyword matches")
        except Exception as exc:
            return ToolResult(self.name, planned_tool.action, "failed", EvidenceBundle(), error=str(exc), observation="Keyword search failed")


class GraphRetrieverTool:
    name = TOOL_GRAPH_RETRIEVER

    def __init__(self, graph_retriever):
        self.graph_retriever = graph_retriever

    def run(self, question: str, planned_tool: PlannedTool, scope: KnowledgeBaseScope | None = None) -> ToolResult:
        if self.graph_retriever is None:
            return ToolResult(self.name, planned_tool.action, "skipped", EvidenceBundle(), observation="GraphRetriever is disabled")
        try:
            result = self._run_graph(question, planned_tool, scope)
            payload = _as_dict(result)
            entities = list(payload.get("entities", []))
            relations = list(payload.get("relations", []))
            paths = list(payload.get("paths", []))
            source_chunk_ids = list(dict.fromkeys(str(chunk_id) for chunk_id in payload.get("source_chunk_ids", []) if chunk_id))
            items = []
            for index, entity in enumerate(entities):
                items.append(
                    EvidenceItem(
                        id=str(entity.get("id") or entity.get("entity_id") or f"entity-{index}"),
                        source_tool=self.name,
                        entity=entity,
                        score=float(payload.get("confidence", 0.0) or 0.0),
                        source_chunk_ids=source_chunk_ids,
                    )
                )
            for index, path in enumerate(paths):
                items.append(
                    EvidenceItem(
                        id=f"path-{index}",
                        source_tool=self.name,
                        graph_path=path,
                        score=float(payload.get("confidence", 0.0) or 0.0),
                        source_chunk_ids=source_chunk_ids,
                    )
                )
            bundle = EvidenceBundle(
                items=items,
                entities=entities,
                relations=relations,
                graph_paths=paths,
                source_chunk_ids=source_chunk_ids,
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                metadata={"graph_result": payload},
            )
            return ToolResult(self.name, planned_tool.action, "completed", bundle, observation=f"{len(entities)} entities, {len(paths)} paths")
        except Exception as exc:
            return ToolResult(self.name, planned_tool.action, "failed", EvidenceBundle(), error=str(exc), observation="Graph retrieval failed")

    def _run_graph(
        self,
        question: str,
        planned_tool: PlannedTool,
        scope: KnowledgeBaseScope | None,
    ):
        if planned_tool.action == "path_search":
            entities = _split_entities(question)
            source = entities[0] if entities else question
            target = entities[1] if len(entities) > 1 else question
            return _call_scoped(
                self.graph_retriever,
                "path_search",
                source,
                target,
                max_depth=planned_tool.limits.get("max_depth", 3),
                scope=scope,
            )
        if planned_tool.action == "neighbor_search":
            entity = (_split_entities(question) or [question])[0]
            return _call_scoped(
                self.graph_retriever,
                "neighbor_search",
                entity,
                depth=planned_tool.limits.get("max_depth", 1),
                scope=scope,
            )
        return _call_scoped(self.graph_retriever, "entity_search", question, scope=scope)


def _hit_to_evidence_item(hit: dict, tool: str, index: int) -> EvidenceItem:
    metadata = hit.get("metadata", {})
    chunk_id = str(metadata.get("chunk_id") or metadata.get("child_id") or "")
    return EvidenceItem(
        id=chunk_id or f"{tool}-{index}",
        source_tool=tool,
        content=str(hit.get("content", "")),
        chunk_id=chunk_id,
        doc_id=str(metadata.get("doc_id", "")),
        parent_id=str(metadata.get("parent_id", "")),
        score=float(hit.get("hybrid_score", hit.get("keyword_score", hit.get("vector_score", 0.0))) or 0.0),
        source_chunk_ids=[chunk_id] if chunk_id else [],
        metadata={**metadata, "route_tool": tool},
    )


def _used_chunks_from_hits(hits: list[dict]) -> list[str]:
    chunks: list[str] = []
    for hit in hits:
        metadata = hit.get("metadata", {})
        chunks.extend(str(chunk_id) for chunk_id in metadata.get("matched_child_ids", []) if chunk_id)
        chunk_id = metadata.get("chunk_id") or metadata.get("child_id")
        if chunk_id:
            chunks.append(str(chunk_id))
    return list(dict.fromkeys(chunks))


def _evidence_source_titles(items: list[EvidenceItem], citations: list[dict[str, Any]] | None = None) -> list[str]:
    titles: list[str] = []
    for citation in citations or []:
        source = str(citation.get("source") or "").strip()
        if source and source.lower() != "unknown":
            titles.append(source)
    for item in items:
        source = str(item.metadata.get("source") or item.metadata.get("storage_path") or item.doc_id or "").strip()
        if source and source.lower() != "unknown":
            titles.append(source)
    return list(dict.fromkeys(titles))


def _max_hit_score(hits: list[dict]) -> float:
    scores = [float(hit.get("hybrid_score", hit.get("keyword_score", hit.get("vector_score", 0.0))) or 0.0) for hit in hits]
    return round(max(scores), 4) if scores else 0.0


def _as_dict(result) -> dict:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return dict(result)


def _split_entities(question: str) -> list[str]:
    for sep in [" depend on ", " depends on ", "依赖"]:
        if sep in question.lower():
            return [part.strip(" ?。") for part in question.split(sep) if part.strip()]
    return [part.strip(" ?。") for part in question.replace("?", "").split(" and ") if part.strip()][:2]


def _call_scoped(target, method_name: str, *args, scope: KnowledgeBaseScope | None = None, **kwargs):
    method = getattr(target, method_name)
    if "scope" in inspect.signature(method).parameters:
        return method(*args, scope=scope, **kwargs)
    if scope is not None and not scope.compatibility_default:
        raise RuntimeError(f"{method_name} does not support knowledge-base scope")
    return method(*args, **kwargs)
