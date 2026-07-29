from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.models.document_models import ParsedImage
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.storage.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


IMAGE_OPERATION_TYPES = {"ocr", "caption"}
IMAGE_OPERATION_STATUSES = {"pending", "processing", "completed", "failed", "canceled"}


class ImageRepository:
    def __init__(self, db_path: str | Path, defaults: DefaultKnowledgeBaseSettings | None = None):
        self.db_path = Path(db_path)
        self.defaults = defaults or DefaultKnowledgeBaseSettings()
        initialize_metadata_database(self.db_path, self.defaults)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_image(
        self,
        doc_id: str,
        image: ParsedImage,
        scope: KnowledgeBaseScope,
        *,
        storage_provider: str = "local",
    ) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            self._assert_document(conn, doc_id, scope)
            conn.execute(
                """insert into document_image_resource
                (id, workspace_id, knowledge_base_id, doc_id, storage_key, storage_provider, source_type, page_number,
                 mime_type, width, height, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (image.image_id, scope.workspace_id, scope.knowledge_base_id, doc_id, image.storage_key,
                 storage_provider, image.source_type, image.page_number, image.mime_type, image.width, image.height,
                 json.dumps(image.metadata, ensure_ascii=False), now),
            )
        return self.get_image(image.image_id, scope)

    def get_image(self, image_id: str, scope: KnowledgeBaseScope) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "select * from document_image_resource where id = ? and workspace_id = ? and knowledge_base_id = ?",
                (image_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
        if not row:
            raise FileNotFoundError(image_id)
        return self._decode_image(row)

    def list_images(self, doc_id: str, scope: KnowledgeBaseScope) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """select * from document_image_resource
                   where doc_id = ? and workspace_id = ? and knowledge_base_id = ?
                   order by page_number, created_at, id""",
                (doc_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchall()
        return [self._decode_image(row) for row in rows]

    def create_operation(self, image_id: str, doc_id: str, operation_type: str, scope: KnowledgeBaseScope) -> dict:
        if operation_type not in IMAGE_OPERATION_TYPES:
            raise ValueError("Unsupported image operation")
        now = datetime.now().isoformat(timespec="seconds")
        operation_id = uuid4().hex
        with self._connect() as conn:
            self._assert_document(conn, doc_id, scope)
            self._assert_image(conn, image_id, doc_id, scope)
            existing = conn.execute(
                """select * from document_image_operation
                   where image_id = ? and workspace_id = ? and knowledge_base_id = ? and operation_type = ?""",
                (image_id, scope.workspace_id, scope.knowledge_base_id, operation_type),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            conn.execute(
                """insert into document_image_operation
                (id, image_id, workspace_id, knowledge_base_id, doc_id, operation_type, status, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (operation_id, image_id, scope.workspace_id, scope.knowledge_base_id, doc_id, operation_type, now, now),
            )
        return self.get_operation(operation_id, scope)

    def get_operation(self, operation_id: str, scope: KnowledgeBaseScope) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "select * from document_image_operation where id = ? and workspace_id = ? and knowledge_base_id = ?",
                (operation_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
        if not row: raise FileNotFoundError(operation_id)
        return dict(row)

    def list_operations(
        self,
        doc_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str | None = None,
    ) -> list[dict]:
        if status is not None and status not in IMAGE_OPERATION_STATUSES:
            raise ValueError("Invalid operation status")
        clauses = ["doc_id = ?", "workspace_id = ?", "knowledge_base_id = ?"]
        params: list[str] = [doc_id, scope.workspace_id, scope.knowledge_base_id]
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        with self._connect() as conn:
            rows = conn.execute(
                f"select * from document_image_operation where {' and '.join(clauses)} order by created_at, id",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def update_operation(
        self,
        operation_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str,
        provider_ref: str = "",
        result_chunk_id: str | None = None,
        error_message: str = "",
        increment_attempt: bool = False,
    ) -> dict:
        if status not in IMAGE_OPERATION_STATUSES:
            raise ValueError("Invalid operation status")
        attempt_assignment = "attempt = attempt + 1," if increment_attempt else ""
        with self._connect() as conn:
            cursor = conn.execute(
                f"""update document_image_operation set status = ?, provider_ref = ?, result_chunk_id = ?,
                   error_message = ?, {attempt_assignment} updated_at = ?
                   where id = ? and workspace_id = ? and knowledge_base_id = ?""",
                (status, provider_ref, result_chunk_id, error_message[:1000], datetime.now().isoformat(timespec="seconds"),
                 operation_id, scope.workspace_id, scope.knowledge_base_id),
            )
            if cursor.rowcount != 1:
                raise FileNotFoundError(operation_id)
        return self.get_operation(operation_id, scope)

    def retry_operation(self, operation_id: str, scope: KnowledgeBaseScope) -> dict:
        operation = self.get_operation(operation_id, scope)
        if operation["status"] in {"processing", "completed"}:
            raise ValueError("Only pending, failed, or canceled image operations can be retried")
        with self._connect() as conn:
            cursor = conn.execute(
                """update document_image_operation
                   set status = 'pending', provider_ref = '', result_chunk_id = null,
                       error_message = '', attempt = attempt + 1, updated_at = ?
                   where id = ? and workspace_id = ? and knowledge_base_id = ?""",
                (datetime.now().isoformat(timespec="seconds"), operation_id, scope.workspace_id, scope.knowledge_base_id),
            )
            if cursor.rowcount != 1:
                raise FileNotFoundError(operation_id)
        return self.get_operation(operation_id, scope)

    def cancel_document_operations(self, doc_id: str, scope: KnowledgeBaseScope) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """update document_image_operation
                   set status = 'canceled', updated_at = ?
                   where doc_id = ? and workspace_id = ? and knowledge_base_id = ?
                     and status in ('pending', 'processing')""",
                (datetime.now().isoformat(timespec="seconds"), doc_id, scope.workspace_id, scope.knowledge_base_id),
            )
            return int(cursor.rowcount)

    def delete_image(self, image_id: str, scope: KnowledgeBaseScope) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """select storage_key from document_image_resource
                   where id = ? and workspace_id = ? and knowledge_base_id = ?""",
                (image_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(image_id)
            conn.execute(
                """delete from document_image_resource
                   where id = ? and workspace_id = ? and knowledge_base_id = ?""",
                (image_id, scope.workspace_id, scope.knowledge_base_id),
            )
        return str(row[0])

    def delete_document_images(self, doc_id: str, scope: KnowledgeBaseScope) -> list[str]:
        with self._connect() as conn:
            keys = [row[0] for row in conn.execute(
                "select storage_key from document_image_resource where doc_id = ? and workspace_id = ? and knowledge_base_id = ?",
                (doc_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchall()]
            conn.execute("delete from document_image_resource where doc_id = ? and workspace_id = ? and knowledge_base_id = ?",
                         (doc_id, scope.workspace_id, scope.knowledge_base_id))
        return keys

    def cleanup_abandoned_staged_resources(self, doc_id: str, scope: KnowledgeBaseScope) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select r.storage_key
                from document_image_resource r
                where r.doc_id = ? and r.workspace_id = ? and r.knowledge_base_id = ?
                  and not exists (
                      select 1
                      from document_image_operation o
                      where o.image_id = r.id
                        and o.workspace_id = r.workspace_id
                        and o.knowledge_base_id = r.knowledge_base_id
                        and o.status in ('processing', 'completed')
                  )
                order by r.created_at, r.id
                """,
                (doc_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchall()
            keys = [str(row[0]) for row in rows]
            if keys:
                placeholders = ",".join("?" for _ in keys)
                conn.execute(
                    f"""delete from document_image_resource
                        where doc_id = ? and workspace_id = ? and knowledge_base_id = ?
                          and storage_key in ({placeholders})""",
                    (doc_id, scope.workspace_id, scope.knowledge_base_id, *keys),
                )
        return keys

    def _assert_document(self, conn: sqlite3.Connection, doc_id: str, scope: KnowledgeBaseScope) -> None:
        row = conn.execute(
            "select 1 from document where id = ? and workspace_id = ? and knowledge_base_id = ?",
            (doc_id, scope.workspace_id, scope.knowledge_base_id),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(doc_id)

    def _assert_image(
        self,
        conn: sqlite3.Connection,
        image_id: str,
        doc_id: str,
        scope: KnowledgeBaseScope,
    ) -> None:
        row = conn.execute(
            """select 1 from document_image_resource
               where id = ? and doc_id = ? and workspace_id = ? and knowledge_base_id = ?""",
            (image_id, doc_id, scope.workspace_id, scope.knowledge_base_id),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(image_id)

    def _decode_image(self, row: sqlite3.Row) -> dict:
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result
