import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class ConversationRepository:
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
                create table if not exists conversation (
                    id text primary key,
                    title text not null,
                    summary text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists conversation_message (
                    id text primary key,
                    conversation_id text not null,
                    role text not null,
                    content text not null,
                    metadata_json text not null,
                    created_at text not null,
                    foreign key(conversation_id) references conversation(id)
                )
                """
            )

    def create_conversation(self, title: str = "") -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        conversation = {
            "id": f"conv_{uuid.uuid4().hex}",
            "title": title,
            "summary": "",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into conversation (id, title, summary, created_at, updated_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    conversation["id"],
                    conversation["title"],
                    conversation["summary"],
                    conversation["created_at"],
                    conversation["updated_at"],
                ),
            )
        return conversation

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from conversation where id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def update_summary(self, conversation_id: str, summary: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "update conversation set summary = ?, updated_at = ? where id = ?",
                (summary, now, conversation_id),
            )

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        message = {
            "id": f"msg_{uuid.uuid4().hex}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "metadata_json": metadata_json or {},
            "created_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into conversation_message
                (id, conversation_id, role, content, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    message["conversation_id"],
                    message["role"],
                    message["content"],
                    json.dumps(message["metadata_json"], ensure_ascii=False),
                    message["created_at"],
                ),
            )
            conn.execute("update conversation set updated_at = ? where id = ?", (now, conversation_id))
        return message

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "select * from conversation_message where conversation_id = ? order by rowid",
                (conversation_id,),
            ).fetchall()
        return [self._decode_message(row) for row in rows]

    def list_recent_messages(self, conversation_id: str, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select * from (
                    select rowid as order_id, * from conversation_message
                    where conversation_id = ?
                    order by rowid desc
                    limit ?
                )
                order by order_id
                """,
                (conversation_id, limit),
            ).fetchall()
        return [self._decode_message(row) for row in rows]

    def _decode_message(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata_json"] = json.loads(data["metadata_json"] or "{}")
        return data
