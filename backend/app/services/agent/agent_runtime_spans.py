from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.services.infrastructure.logging_config import sanitize_payload
from app.services.storage.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


@dataclass(frozen=True)
class AgentRuntimeSpan:
    run_id: str
    span_id: str
    name: str
    kind: str
    started_clock: float


class AgentRuntimeSpanRepository:
    def __init__(self, db_path: Path | str, defaults: DefaultKnowledgeBaseSettings | None = None, enabled: bool = True):
        self.enabled = bool(enabled)
        self.db_path = Path(db_path)
        self.defaults = defaults or DefaultKnowledgeBaseSettings()
        if self.enabled:
            initialize_metadata_database(self.db_path, self.defaults)

    @classmethod
    def disabled(cls) -> "AgentRuntimeSpanRepository":
        return cls(":memory:", enabled=False)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def start_span(
        self,
        *,
        run_id: str,
        name: str,
        kind: str,
        parent_span_id: str = "",
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRuntimeSpan | None:
        if not self.enabled:
            return None
        span_id = uuid4().hex
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into agent_runtime_spans(
                    run_id, span_id, parent_span_id, name, kind, status,
                    input_json, output_json, metadata_json, error_message,
                    started_at, finished_at, duration_ms, created_at, updated_at
                ) values (?, ?, ?, ?, ?, 'running', ?, '{}', ?, '', ?, null, 0, ?, ?)
                """,
                (
                    run_id,
                    span_id,
                    parent_span_id,
                    name,
                    kind,
                    _json(input or {}),
                    _json(metadata or {}),
                    now,
                    now,
                    now,
                ),
            )
            conn.commit()
        return AgentRuntimeSpan(run_id=run_id, span_id=span_id, name=name, kind=kind, started_clock=perf_counter())

    def finish_span(
        self,
        span: AgentRuntimeSpan | None,
        *,
        status: str = "completed",
        output: dict[str, Any] | None = None,
        error_message: str = "",
    ) -> None:
        if not self.enabled or span is None:
            return
        with self._connect() as conn:
            conn.execute(
                """
                update agent_runtime_spans
                set status = ?, output_json = ?, error_message = ?, finished_at = ?,
                    duration_ms = ?, updated_at = ?
                where span_id = ?
                """,
                (
                    status,
                    _json(output or {}),
                    str(error_message or "")[:2000],
                    _utc_now(),
                    max(0, int((perf_counter() - span.started_clock) * 1000)),
                    _utc_now(),
                    span.span_id,
                ),
            )
            conn.commit()


def _json(value: dict[str, Any]) -> str:
    return json.dumps(sanitize_payload(value, limit=2000), ensure_ascii=False)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
