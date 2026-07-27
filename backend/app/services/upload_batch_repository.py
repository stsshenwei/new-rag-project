from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.knowledge_base import KnowledgeBaseScope
from app.services.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


BATCH_STATUSES = {
    "draft",
    "uploading",
    "ready_to_process",
    "processing",
    "completed",
    "partial_failed",
    "failed",
    "canceled",
}
FILE_STATUSES = {
    "pending",
    "uploaded",
    "parsing",
    "indexed",
    "enrichment_pending",
    "completed",
    "failed",
    "canceled",
}
TERMINAL_BATCH_STATUSES = {"completed", "partial_failed", "failed", "canceled"}
PROCESSING_PHASES = ("parse", "chunk", "index", "multimodal", "postprocess")


class UploadBatchRepository:
    def __init__(self, db_path: Path | str, defaults: DefaultKnowledgeBaseSettings | None = None):
        self.db_path = Path(db_path)
        self.defaults = defaults or DefaultKnowledgeBaseSettings()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def create_batch(self, scope: KnowledgeBaseScope, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        batch_id = f"upload-{uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            self._assert_active_knowledge_base(conn, scope)
            conn.execute(
                """
                insert into knowledge_upload_batch(
                    id, workspace_id, knowledge_base_id, status, settings_json, error_message,
                    created_at, updated_at, confirmed_at, completed_at
                ) values (?, ?, ?, 'draft', ?, '', ?, ?, null, null)
                """,
                (
                    batch_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    json.dumps(settings or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get_batch(batch_id, scope)

    def get_batch(self, batch_id: str, scope: KnowledgeBaseScope) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from knowledge_upload_batch
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (batch_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
            if row is None:
                raise KeyError(batch_id)
            files = conn.execute(
                """
                select * from knowledge_upload_file
                where batch_id = ? and workspace_id = ? and knowledge_base_id = ?
                order by created_at, id
                """,
                (batch_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchall()
        data = self._decode_batch(row)
        decoded_files = [self._decode_file(file_row) for file_row in files]
        data["files"] = decoded_files
        data["aggregate"] = _aggregate(decoded_files)
        return data

    def list_batches(self, scope: KnowledgeBaseScope, include_terminal: bool = True) -> list[dict[str, Any]]:
        clauses = ["workspace_id = ?", "knowledge_base_id = ?"]
        params: list[Any] = [scope.workspace_id, scope.knowledge_base_id]
        if not include_terminal:
            placeholders = ",".join("?" for _ in TERMINAL_BATCH_STATUSES)
            clauses.append(f"status not in ({placeholders})")
            params.extend(sorted(TERMINAL_BATCH_STATUSES))
        with self._connect() as conn:
            rows = conn.execute(
                f"select * from knowledge_upload_batch where {' and '.join(clauses)} order by updated_at desc",
                params,
            ).fetchall()
        return [self.get_batch(str(row["id"]), scope) for row in rows]

    def update_batch(
        self,
        batch_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str | None = None,
        settings: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        if status is not None and status not in BATCH_STATUSES:
            raise ValueError("Unsupported upload batch status")
        assignments = ["updated_at = ?"]
        values: list[Any] = [_now()]
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
            if status == "processing":
                assignments.append("confirmed_at = coalesce(confirmed_at, ?)")
                values.append(_now())
            if status in TERMINAL_BATCH_STATUSES:
                assignments.append("completed_at = coalesce(completed_at, ?)")
                values.append(_now())
        if settings is not None:
            assignments.append("settings_json = ?")
            values.append(json.dumps(settings, ensure_ascii=False))
        if error_message is not None:
            assignments.append("error_message = ?")
            values.append(_sanitize_error(error_message))
        values.extend([batch_id, scope.workspace_id, scope.knowledge_base_id])
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                update knowledge_upload_batch
                set {', '.join(assignments)}
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                values,
            )
            if cursor.rowcount == 0:
                raise KeyError(batch_id)
        return self.get_batch(batch_id, scope)

    def add_file(
        self,
        batch_id: str,
        scope: KnowledgeBaseScope,
        *,
        original_name: str,
        relative_path: str,
        storage_path: str,
        size: int,
    ) -> dict[str, Any]:
        file_id = f"upload-file-{uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            batch = conn.execute(
                """
                select status from knowledge_upload_batch
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (batch_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
            if batch is None:
                raise KeyError(batch_id)
            if str(batch["status"]) not in {"draft", "uploading", "ready_to_process"}:
                raise ValueError("Upload batch does not accept more files")
            conn.execute(
                """
                insert into knowledge_upload_file(
                    id, batch_id, workspace_id, knowledge_base_id, original_name, relative_path,
                    storage_path, size, status, document_id, chunks, error_message, phases_json,
                    warnings_json, errors_json, retry_eligible, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', null, 0, '', ?, '[]', '[]', 0, ?, ?)
                """,
                (
                    file_id,
                    batch_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    original_name,
                    relative_path,
                    storage_path,
                    int(size),
                    json.dumps(initial_phase_report(), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                update knowledge_upload_batch
                set status = case when status = 'draft' then 'uploading' else status end,
                    updated_at = ?
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (now, batch_id, scope.workspace_id, scope.knowledge_base_id),
            )
        return self.get_file(file_id, scope)

    def get_file(self, file_id: str, scope: KnowledgeBaseScope) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from knowledge_upload_file
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (file_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
        if row is None:
            raise KeyError(file_id)
        return self._decode_file(row)

    def update_file(
        self,
        file_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str | None = None,
        document_id: str | None = None,
        chunks: int | None = None,
        error_message: str | None = None,
        phases: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        retry_eligible: bool | None = None,
    ) -> dict[str, Any]:
        if status is not None and status not in FILE_STATUSES:
            raise ValueError("Unsupported upload file status")
        assignments = ["updated_at = ?"]
        values: list[Any] = [_now()]
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if document_id is not None:
            assignments.append("document_id = ?")
            values.append(document_id)
        if chunks is not None:
            assignments.append("chunks = ?")
            values.append(int(chunks))
        if error_message is not None:
            assignments.append("error_message = ?")
            values.append(_sanitize_error(error_message))
        if phases is not None:
            assignments.append("phases_json = ?")
            values.append(json.dumps(_normalize_phases(phases), ensure_ascii=False))
        if warnings is not None:
            assignments.append("warnings_json = ?")
            values.append(json.dumps([_sanitize_error(item) for item in warnings], ensure_ascii=False))
        if errors is not None:
            assignments.append("errors_json = ?")
            values.append(json.dumps([_sanitize_error(item) for item in errors], ensure_ascii=False))
        if retry_eligible is not None:
            assignments.append("retry_eligible = ?")
            values.append(1 if retry_eligible else 0)
        values.extend([file_id, scope.workspace_id, scope.knowledge_base_id])
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                update knowledge_upload_file
                set {', '.join(assignments)}
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                values,
            )
            if cursor.rowcount == 0:
                raise KeyError(file_id)
        return self.get_file(file_id, scope)

    def list_files(self, batch_id: str, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        return list(self.get_batch(batch_id, scope)["files"])

    def cancel_batch(self, batch_id: str, scope: KnowledgeBaseScope) -> dict[str, Any]:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update knowledge_upload_batch
                set status = 'canceled', updated_at = ?, completed_at = coalesce(completed_at, ?)
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (now, now, batch_id, scope.workspace_id, scope.knowledge_base_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(batch_id)
            conn.execute(
                """
                update knowledge_upload_file
                set status = 'canceled', updated_at = ?
                where batch_id = ? and workspace_id = ? and knowledge_base_id = ?
                  and status in ('pending', 'uploaded')
                """,
                (now, batch_id, scope.workspace_id, scope.knowledge_base_id),
            )
        return self.get_batch(batch_id, scope)

    def _assert_active_knowledge_base(self, conn: sqlite3.Connection, scope: KnowledgeBaseScope) -> None:
        row = conn.execute(
            """
            select 1 from knowledge_base
            where id = ? and workspace_id = ? and status = 'active'
            """,
            (scope.knowledge_base_id, scope.workspace_id),
        ).fetchone()
        if row is None:
            raise ValueError("Knowledge base does not exist, is archived, or belongs to another workspace")

    def _decode_batch(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["settings"] = json.loads(data.pop("settings_json") or "{}")
        return data

    def _decode_file(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["phases"] = _normalize_phases(_json_list(data.pop("phases_json", "[]")))
        data["warnings"] = [_sanitize_error(item) for item in _json_list(data.pop("warnings_json", "[]"))]
        data["errors"] = [_sanitize_error(item) for item in _json_list(data.pop("errors_json", "[]"))]
        data["retry_eligible"] = bool(data.get("retry_eligible", 0))
        return data


def _aggregate(files: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(files),
        "uploaded": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "canceled": 0,
    }
    for item in files:
        status = str(item.get("status", ""))
        if status in {"uploaded", "pending"}:
            counts["uploaded"] += 1
        elif status in {"parsing", "indexed", "enrichment_pending"}:
            counts["processing"] += 1
        elif status == "completed":
            counts["completed"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "canceled":
            counts["canceled"] += 1
    return counts


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sanitize_error(message: str) -> str:
    return " ".join(str(message).split())[:500]


def initial_phase_report() -> list[dict[str, Any]]:
    return [
        {"name": phase, "status": "pending", "warnings": [], "errors": [], "retry_eligible": False}
        for phase in PROCESSING_PHASES
    ]


def _normalize_phases(phases: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    by_name = {str(item.get("name", "")): dict(item) for item in phases if isinstance(item, dict)}
    normalized: list[dict[str, Any]] = []
    for phase in PROCESSING_PHASES:
        item = by_name.get(phase, {})
        normalized.append(
            {
                "name": phase,
                "status": str(item.get("status") or "pending"),
                "warnings": [_sanitize_error(value) for value in item.get("warnings", []) if str(value)],
                "errors": [_sanitize_error(value) for value in item.get("errors", []) if str(value)],
                "retry_eligible": bool(item.get("retry_eligible", False)),
            }
        )
    return normalized


def _json_list(raw: str) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
