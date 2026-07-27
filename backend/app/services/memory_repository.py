import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists memory (
                    id text primary key,
                    scope text not null,
                    type text not null,
                    normalized_key text not null,
                    content text not null,
                    confidence real not null,
                    status text not null,
                    source_conversation_id text,
                    source_message_id text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create unique index if not exists idx_memory_active_key
                on memory(scope, normalized_key, status)
                """
            )

    def upsert_memory(
        self,
        scope: str,
        memory_type: str,
        normalized_key: str,
        content: str,
        confidence: float,
        source_conversation_id: str | None = None,
        source_message_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                """
                select * from memory
                where scope = ? and normalized_key = ? and status = 'active'
                """,
                (scope, normalized_key),
            ).fetchone()
            if existing:
                memory_id = str(existing["id"])
                created_at = str(existing["created_at"])
            else:
                memory_id = f"mem_{uuid.uuid4().hex}"
                created_at = now
            conn.execute(
                """
                insert or replace into memory
                (id, scope, type, normalized_key, content, confidence, status,
                 source_conversation_id, source_message_id, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    scope,
                    memory_type,
                    normalized_key,
                    content,
                    confidence,
                    source_conversation_id,
                    source_message_id,
                    created_at,
                    now,
                ),
            )
        loaded = self.get_memory(memory_id)
        if loaded is None:
            raise RuntimeError("Failed to upsert memory")
        return loaded

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from memory where id = ?", (memory_id,)).fetchone()
        return dict(row) if row else None

    def list_active_memories(self, scope: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = "where status = 'active'"
        if scope:
            where += " and scope = ?"
            params.append(scope)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"select * from memory {where} order by updated_at desc, id", params).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                "update memory set status = 'deleted', updated_at = ? where id = ? and status != 'deleted'",
                (now, memory_id),
            )
        return cursor.rowcount > 0
