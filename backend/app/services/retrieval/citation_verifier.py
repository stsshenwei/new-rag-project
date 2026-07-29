from __future__ import annotations

import inspect
from typing import Any

from app.models.agentic_retrieval import VerificationResult
from app.models.knowledge_base import KnowledgeBaseScope


class CitationVerifier:
    def __init__(self, document_repository):
        self.document_repository = document_repository

    def verify(
        self,
        citations: list[dict[str, Any]] | None = None,
        used_chunks: list[str] | None = None,
        graph_paths: list[dict[str, Any]] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> VerificationResult:
        verified_citations: list[str] = []
        invalid_citations: list[str] = []
        verified_chunks: list[str] = []
        invalid_chunks: list[str] = []
        invalid_graph: list[str] = []

        for citation in citations or []:
            chunk_id = self._citation_chunk_id(citation)
            if not chunk_id:
                invalid_citations.append("")
            elif self._chunk_exists(chunk_id, scope):
                verified_citations.append(chunk_id)
            else:
                invalid_citations.append(chunk_id)

        for chunk_id in used_chunks or []:
            if self._chunk_exists(chunk_id, scope):
                verified_chunks.append(chunk_id)
            else:
                invalid_chunks.append(chunk_id)

        for path in graph_paths or []:
            for relation in self._path_relations(path):
                source_chunk_id = str(relation.get("source_chunk_id") or "")
                if not source_chunk_id or not self._chunk_exists(source_chunk_id, scope):
                    invalid_graph.append(source_chunk_id)
                else:
                    verified_chunks.append(source_chunk_id)

        valid = not invalid_citations and not invalid_chunks and not invalid_graph
        summary = "all citations verified" if valid else "invalid citation or graph evidence found"
        return VerificationResult(
            valid=valid,
            verified_citations=list(dict.fromkeys(verified_citations)),
            invalid_citations=list(dict.fromkeys(invalid_citations)),
            verified_chunks=list(dict.fromkeys(verified_chunks)),
            invalid_chunks=list(dict.fromkeys(invalid_chunks)),
            invalid_graph_source_chunks=list(dict.fromkeys(invalid_graph)),
            summary=summary,
            metadata={
                "checked_citations": len(citations or []),
                "checked_graph_paths": len(graph_paths or []),
                "knowledge_base_scope": scope.to_dict() if scope is not None else None,
            },
        )

    def _citation_chunk_id(self, citation: dict[str, Any]) -> str:
        return str(citation.get("chunk_id") or citation.get("child_id") or citation.get("parent_id") or "")

    def _chunk_exists(self, chunk_id: str, scope: KnowledgeBaseScope | None = None) -> bool:
        if not chunk_id:
            return False
        try:
            method = self.document_repository.get_chunk
            if "scope" in inspect.signature(method).parameters:
                return bool(method(chunk_id, scope=scope))
            if scope is not None and not scope.compatibility_default:
                return False
            return bool(method(chunk_id))
        except Exception:
            return False

    def _path_relations(self, path: dict[str, Any]) -> list[dict[str, Any]]:
        relations = path.get("relations", [])
        if isinstance(relations, list):
            return [relation for relation in relations if isinstance(relation, dict)]
        return []
