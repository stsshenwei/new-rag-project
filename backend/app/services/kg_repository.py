import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.kg_models import EntityMention
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


class KGRepository:
    def __init__(self, db_path: Path | str, defaults: DefaultKnowledgeBaseSettings | None = None):
        self.db_path = Path(db_path)
        self.defaults = defaults or DefaultKnowledgeBaseSettings()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_metadata_database(self.db_path, self.defaults)

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

    def create_extraction_task(
        self,
        doc_id: str,
        extractor_version: str,
        parent_chunk_count: int = 0,
        metadata: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> dict[str, Any]:
        scope = scope or KnowledgeBaseScope(
            self.defaults.workspace_id,
            (self.defaults.knowledge_base_id,),
            compatibility_default=True,
        )
        now = datetime.now().isoformat(timespec="seconds")
        task_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                insert into kg_extraction_task
                (id, doc_id, workspace_id, knowledge_base_id, status, error_message, extractor_version, parent_chunk_count,
                 metadata_json, started_at, finished_at, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    doc_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    "pending",
                    None,
                    extractor_version,
                    parent_chunk_count,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    None,
                    None,
                    now,
                ),
            )
        return self.get_task(task_id) or {}

    def mark_task_started(self, task_id: str) -> None:
        self._update_task(task_id, status="running", started_at=datetime.now().isoformat(timespec="seconds"))

    def mark_task_completed(self, task_id: str) -> None:
        self._update_task(task_id, status="completed", finished_at=datetime.now().isoformat(timespec="seconds"), error_message=None)

    def mark_task_failed(self, task_id: str, error_message: str) -> None:
        self._update_task(task_id, status="failed", finished_at=datetime.now().isoformat(timespec="seconds"), error_message=error_message)

    def mark_task_partial_failed(self, task_id: str, error_message: str) -> None:
        self._update_task(task_id, status="partial_failed", finished_at=datetime.now().isoformat(timespec="seconds"), error_message=error_message)

    def _update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values())
        values.append(task_id)
        with self._connect() as conn:
            conn.execute(f"update kg_extraction_task set {assignments} where id = ?", values)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from kg_extraction_task where id = ?", (task_id,)).fetchone()
        return self._decode_row(row) if row else None

    def list_extraction_tasks(
        self,
        doc_id: str | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if doc_id:
            clauses.append("doc_id = ?")
            params.append(doc_id)
        if scope is not None:
            placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
            clauses.extend(["workspace_id = ?", f"knowledge_base_id in ({placeholders})"])
            params.extend([scope.workspace_id, *scope.selected_knowledge_base_ids])
        where = f" where {' and '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"select * from kg_extraction_task{where} order by created_at desc", params).fetchall()
        return [self._decode_row(row) for row in rows]

    def insert_entity_mentions(self, mentions: list[EntityMention]) -> None:
        if not mentions:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                insert or replace into entity_mention
                (id, workspace_id, knowledge_base_id, entity_id, entity_type, entity_name, doc_id, chunk_id, parent_id,
                 page_start, page_end, mention_text, confidence, aliases_json, description,
                 metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        mention.id,
                        str(mention.metadata.get("workspace_id", self.defaults.workspace_id)),
                        str(mention.metadata.get("knowledge_base_id", self.defaults.knowledge_base_id)),
                        mention.entity_id,
                        mention.entity_type,
                        mention.entity_name,
                        mention.doc_id,
                        mention.chunk_id,
                        mention.parent_id,
                        mention.page_start,
                        mention.page_end,
                        mention.mention_text,
                        mention.confidence,
                        json.dumps(mention.aliases, ensure_ascii=False),
                        mention.description,
                        json.dumps(mention.metadata, ensure_ascii=False),
                        mention.created_at,
                    )
                    for mention in mentions
                ],
            )

    def list_entity_mentions(
        self,
        doc_id: str | None = None,
        entity_id: str | None = None,
        chunk_id: str | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if doc_id:
            clauses.append("doc_id = ?")
            params.append(doc_id)
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if chunk_id:
            clauses.append("chunk_id = ?")
            params.append(chunk_id)
        if scope is not None:
            placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
            clauses.extend(["workspace_id = ?", f"knowledge_base_id in ({placeholders})"])
            params.extend([scope.workspace_id, *scope.selected_knowledge_base_ids])
        where = f" where {' and '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"select * from entity_mention{where} order by created_at, id", params).fetchall()
        return [self._decode_row(row) for row in rows]

    def upsert_community_summary(
        self,
        community_id: str,
        summary: str,
        entity_ids: list[str],
        source_chunk_ids: list[str],
        confidence: float,
        metadata: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> None:
        scope = scope or KnowledgeBaseScope(
            self.defaults.workspace_id,
            (self.defaults.knowledge_base_id,),
            compatibility_default=True,
        )
        now = datetime.now().isoformat(timespec="seconds")
        row_id = f"{scope.knowledge_base_id}:{community_id}"
        with self._connect() as conn:
            existing = conn.execute("select created_at from graph_community_summary where id = ?", (row_id,)).fetchone()
            created_at = str(existing[0]) if existing else now
            conn.execute(
                """
                insert or replace into graph_community_summary
                (id, workspace_id, knowledge_base_id, community_id, summary, entity_ids_json, source_chunk_ids_json,
                 confidence, metadata_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    community_id,
                    summary,
                    json.dumps(entity_ids, ensure_ascii=False),
                    json.dumps(source_chunk_ids, ensure_ascii=False),
                    confidence,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at,
                    now,
                ),
            )

    def list_community_summaries(self, scope: KnowledgeBaseScope | None = None) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if scope is not None:
            placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
            where = f" where workspace_id = ? and knowledge_base_id in ({placeholders})"
            params = [scope.workspace_id, *scope.selected_knowledge_base_ids]
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"select * from graph_community_summary{where} order by updated_at desc", params
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ["metadata_json", "aliases_json", "entity_ids_json", "source_chunk_ids_json"]:
            if key in data:
                default = "[]" if key.endswith("_ids_json") or key == "aliases_json" else "{}"
                data[key] = json.loads(data[key] or default)
        return data
