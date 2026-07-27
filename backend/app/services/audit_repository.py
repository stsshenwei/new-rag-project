from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.knowledge_base import KnowledgeBaseScope
from app.services.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


class KnowledgeAuditRepository:
    def __init__(
        self,
        db_path: Path | str,
        defaults: DefaultKnowledgeBaseSettings | None = None,
    ):
        self.db_path = Path(db_path)
        self.defaults = defaults or DefaultKnowledgeBaseSettings()
        initialize_metadata_database(self.db_path, self.defaults)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("begin")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def start_query(self, question: str, scope: KnowledgeBaseScope, query_type: str = "") -> str:
        query_id = f"query-{uuid.uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into query_log(
                    id, workspace_id, knowledge_base_ids_json, question, status, query_type,
                    tool_calls_json, citation_chunk_ids_json, response_metadata_json,
                    error_message, created_at, finished_at
                ) values (?, ?, ?, ?, 'running', ?, '[]', '[]', '{}', '', ?, null)
                """,
                (
                    query_id,
                    scope.workspace_id,
                    json.dumps(list(scope.selected_knowledge_base_ids), ensure_ascii=False),
                    question,
                    query_type,
                    now,
                ),
            )
        return query_id

    def finish_query(
        self,
        query_id: str,
        *,
        status: str,
        tool_calls: list[dict[str, Any]] | None = None,
        citation_chunk_ids: list[str] | None = None,
        response_metadata: dict[str, Any] | None = None,
        error_message: str = "",
    ) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update query_log
                set status = ?, tool_calls_json = ?, citation_chunk_ids_json = ?,
                    response_metadata_json = ?, error_message = ?, finished_at = ?
                where id = ?
                """,
                (
                    status,
                    json.dumps(tool_calls or [], ensure_ascii=False),
                    json.dumps(list(dict.fromkeys(citation_chunk_ids or [])), ensure_ascii=False),
                    json.dumps(response_metadata or {}, ensure_ascii=False),
                    error_message[:1000],
                    _now(),
                    query_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(query_id)

    def create_feedback(
        self,
        scope: KnowledgeBaseScope,
        *,
        correction: str,
        query_log_id: str | None = None,
        rating: str = "correction",
        source_chunk_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        feedback_id = f"feedback-{uuid.uuid4().hex}"
        with self._connect() as conn:
            if query_log_id:
                query = conn.execute(
                    "select workspace_id, knowledge_base_ids_json from query_log where id = ?", (query_log_id,)
                ).fetchone()
                if query is None:
                    raise KeyError(query_log_id)
                query_kbs = set(json.loads(query[1] or "[]"))
                if str(query[0]) != scope.workspace_id or scope.knowledge_base_id not in query_kbs:
                    raise ValueError("Feedback target is outside the query knowledge base scope")
            conn.execute(
                """
                insert into answer_feedback(
                    id, query_log_id, workspace_id, knowledge_base_id, rating, correction,
                    source_chunk_ids_json, metadata_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    query_log_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    rating,
                    correction,
                    json.dumps(list(dict.fromkeys(source_chunk_ids or [])), ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    _now(),
                ),
            )
        return self.get_feedback(feedback_id, scope)

    def get_query(self, query_id: str, scope: KnowledgeBaseScope) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select * from query_log where id = ? and workspace_id = ?", (query_id, scope.workspace_id)
            ).fetchone()
        if row is None:
            return None
        data = _decode_query(row)
        if not set(data["knowledge_base_ids"]).issubset(set(scope.selected_knowledge_base_ids)):
            return None
        return data

    def list_queries(self, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from query_log where workspace_id = ? order by created_at, id",
                (scope.workspace_id,),
            ).fetchall()
        allowed = set(scope.selected_knowledge_base_ids)
        return [
            data
            for row in rows
            if set((data := _decode_query(row))["knowledge_base_ids"]).issubset(allowed)
        ]

    def get_feedback(self, feedback_id: str, scope: KnowledgeBaseScope) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from answer_feedback
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (feedback_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
        if row is None:
            raise KeyError(feedback_id)
        return _decode_feedback(row)

    def list_feedback(self, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select * from answer_feedback
                where workspace_id = ? and knowledge_base_id in ({placeholders})
                order by created_at
                """,
                (scope.workspace_id, *scope.selected_knowledge_base_ids),
            ).fetchall()
        return [_decode_feedback(row) for row in rows]


def _decode_query(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["knowledge_base_ids"] = json.loads(data.pop("knowledge_base_ids_json") or "[]")
    data["tool_calls"] = json.loads(data.pop("tool_calls_json") or "[]")
    data["citation_chunk_ids"] = json.loads(data.pop("citation_chunk_ids_json") or "[]")
    data["response_metadata"] = json.loads(data.pop("response_metadata_json") or "{}")
    return data


def _decode_feedback(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["source_chunk_ids"] = json.loads(data.pop("source_chunk_ids_json") or "[]")
    data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    return data


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
