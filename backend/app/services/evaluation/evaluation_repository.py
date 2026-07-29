from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.evaluation import EvalResultRecord
from app.services.storage.storage_schema import initialize_evaluation_database


class EvaluationRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_evaluation_database(self.db_path)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
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

    def create_run(
        self,
        dataset_id: str,
        dataset_version: str,
        dataset_path: str,
        config_snapshot: dict[str, Any] | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        now = _now()
        run_id = f"eval-run-{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                insert into eval_run
                (id, dataset_id, dataset_version, dataset_path, status, started_at, finished_at,
                 created_at, updated_at, config_snapshot, aggregate_scores, report_paths, error_message,
                 knowledge_base_ids_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    dataset_id,
                    dataset_version,
                    dataset_path,
                    "running",
                    now,
                    None,
                    now,
                    now,
                    _dump(config_snapshot or {}),
                    _dump({}),
                    _dump({}),
                    "",
                    _dump(knowledge_base_ids or []),
                ),
            )
        return self.get_run(run_id)

    def update_run(self, run_id: str, **updates: Any) -> dict[str, Any]:
        allowed = {"status", "finished_at", "aggregate_scores", "report_paths", "error_message", "config_snapshot"}
        fields = []
        params = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            fields.append(f"{key} = ?")
            params.append(_dump(value) if key in {"aggregate_scores", "report_paths", "config_snapshot"} else value)
        if not fields:
            return self.get_run(run_id)
        fields.append("updated_at = ?")
        params.append(_now())
        params.append(run_id)
        with self._connect() as conn:
            conn.execute(f"update eval_run set {', '.join(fields)} where id = ?", params)
        return self.get_run(run_id)

    def finish_run(self, run_id: str, status: str, aggregate_scores: dict[str, Any] | None = None, report_paths: dict[str, str] | None = None, error_message: str = "") -> dict[str, Any]:
        return self.update_run(
            run_id,
            status=status,
            finished_at=_now(),
            aggregate_scores=aggregate_scores or {},
            report_paths=report_paths or {},
            error_message=error_message,
        )

    def add_result(self, result: EvalResultRecord) -> dict[str, Any]:
        result_id = result.id or f"eval-result-{uuid.uuid4().hex[:12]}"
        now = result.created_at or _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into eval_result
                (id, run_id, case_id, status, question, query_type, tags, case_snapshot, answer,
                 response_snapshot, evidence_snapshot, metric_scores, latency_ms, error_message, created_at,
                 knowledge_base_ids_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    result.run_id,
                    result.case_id,
                    result.status,
                    result.question,
                    result.query_type,
                    _dump(result.tags),
                    _dump(result.case_snapshot),
                    result.answer,
                    _dump(result.response_snapshot),
                    _dump(result.evidence_snapshot),
                    _dump(result.metric_scores),
                    float(result.latency_ms or 0.0),
                    result.error_message,
                    now,
                    _dump(result.knowledge_base_ids),
                ),
            )
        return self.get_result(result_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from eval_run where id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Evaluation run not found: {run_id}")
        return self._decode_run(row)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("select * from eval_run order by updated_at desc").fetchall()
        return [self._decode_run(row) for row in rows]

    def get_result(self, result_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from eval_result where id = ?", (result_id,)).fetchone()
        if row is None:
            raise KeyError(f"Evaluation result not found: {result_id}")
        return self._decode_result(row)

    def list_results(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("select * from eval_result where run_id = ? order by created_at, case_id", (run_id,)).fetchall()
        return [self._decode_result(row) for row in rows]

    def _decode_run(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("config_snapshot", "aggregate_scores", "report_paths"):
            data[key] = json.loads(data[key] or "{}")
        data["knowledge_base_ids"] = json.loads(data.pop("knowledge_base_ids_json", "[]") or "[]")
        return data

    def _decode_result(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key, default in {
            "tags": [],
            "case_snapshot": {},
            "response_snapshot": {},
            "evidence_snapshot": {},
            "metric_scores": {},
        }.items():
            data[key] = json.loads(data[key] or _dump(default))
        data["knowledge_base_ids"] = json.loads(data.pop("knowledge_base_ids_json", "[]") or "[]")
        return data


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
