import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.document_models import Chunk
from app.models.knowledge_base import KnowledgeBaseScope
from app.models.processing_config import PROCESSING_VERSION
from app.services.storage_schema import DefaultKnowledgeBaseSettings, initialize_metadata_database


class DocumentRepository:
    KEYWORD_CHUNK_TYPES = {"child", "table", "ocr", "image_ocr", "image_caption"}

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

    def upsert_document(
        self,
        id: str,
        name: str,
        file_type: str,
        storage_path: str,
        parse_status: str,
        metadata_json: dict[str, Any] | None = None,
        workspace_id: str | None = None,
        knowledge_base_id: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        metadata_json = metadata_json or {}
        workspace_id = (workspace_id or self.defaults.workspace_id).strip()
        knowledge_base_id = (knowledge_base_id or self.defaults.knowledge_base_id).strip()
        with self._connect() as conn:
            self._assert_active_knowledge_base(conn, workspace_id, knowledge_base_id)
            existing = conn.execute(
                "select workspace_id, knowledge_base_id, created_at from document where id = ?", (id,)
            ).fetchone()
            if existing is not None and (str(existing[0]), str(existing[1])) != (workspace_id, knowledge_base_id):
                raise ValueError("Document ownership is immutable")
            created_at = str(existing[2]) if existing else now
            conn.execute(
                """
                insert into document
                (id, workspace_id, knowledge_base_id, name, file_type, storage_path, parse_status,
                 created_at, updated_at, metadata_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    name = excluded.name,
                    file_type = excluded.file_type,
                    storage_path = excluded.storage_path,
                    parse_status = excluded.parse_status,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    id,
                    workspace_id,
                    knowledge_base_id,
                    name,
                    file_type,
                    storage_path,
                    parse_status,
                    created_at,
                    now,
                    json.dumps(metadata_json, ensure_ascii=False),
                ),
            )

    def replace_chunks(
        self,
        doc_id: str,
        chunks: list[Chunk],
        scope: KnowledgeBaseScope | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            document = conn.execute(
                "select workspace_id, knowledge_base_id from document where id = ?", (doc_id,)
            ).fetchone()
            if document is None:
                raise ValueError(f"Cannot write chunks for missing document {doc_id!r}")
            workspace_id = str(document[0])
            knowledge_base_id = str(document[1])
            if scope is not None and not scope.contains(workspace_id, knowledge_base_id):
                raise ValueError("Document is outside the active knowledge base scope")
            for chunk in chunks:
                if chunk.doc_id != doc_id:
                    raise ValueError(f"Chunk {chunk.id!r} belongs to a different document")
                chunk_workspace = str(chunk.metadata.get("workspace_id", workspace_id))
                chunk_knowledge_base = str(chunk.metadata.get("knowledge_base_id", knowledge_base_id))
                if chunk_workspace != workspace_id or chunk_knowledge_base != knowledge_base_id:
                    raise ValueError(f"Chunk {chunk.id!r} ownership does not match document")
            conn.execute("delete from document_chunk where doc_id = ?", (doc_id,))
            conn.execute("delete from document_chunk_fts where doc_id = ?", (doc_id,))
            chunk_rows = [(chunk, self._normalized_chunk_metadata(chunk)) for chunk in chunks]
            conn.executemany(
                """
                insert into document_chunk
                (id, doc_id, workspace_id, knowledge_base_id, parent_id, chunk_type, title_path, content, content_markdown,
                 page_start, page_end, token_count, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.doc_id,
                        workspace_id,
                        knowledge_base_id,
                        chunk.parent_id,
                        chunk.chunk_type,
                        chunk.title_path,
                        chunk.content,
                        chunk.content_markdown,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.token_count,
                        json.dumps(metadata, ensure_ascii=False),
                        now,
                    )
                    for chunk, metadata in chunk_rows
                ],
            )
            self._insert_keyword_rows(conn, chunks)

    def upsert_chunks(
        self,
        doc_id: str,
        chunks: list[Chunk],
        scope: KnowledgeBaseScope | None = None,
    ) -> None:
        if not chunks:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            document = conn.execute(
                "select workspace_id, knowledge_base_id from document where id = ?", (doc_id,)
            ).fetchone()
            if document is None:
                raise ValueError(f"Cannot write chunks for missing document {doc_id!r}")
            workspace_id = str(document[0])
            knowledge_base_id = str(document[1])
            if scope is not None and not scope.contains(workspace_id, knowledge_base_id):
                raise ValueError("Document is outside the active knowledge base scope")
            for chunk in chunks:
                if chunk.doc_id != doc_id:
                    raise ValueError(f"Chunk {chunk.id!r} belongs to a different document")
                chunk_workspace = str(chunk.metadata.get("workspace_id", workspace_id))
                chunk_knowledge_base = str(chunk.metadata.get("knowledge_base_id", knowledge_base_id))
                if chunk_workspace != workspace_id or chunk_knowledge_base != knowledge_base_id:
                    raise ValueError(f"Chunk {chunk.id!r} ownership does not match document")

            chunk_ids = [chunk.id for chunk in chunks]
            placeholders = ",".join("?" for _ in chunk_ids)
            conn.execute(
                f"delete from document_chunk_fts where id in ({placeholders})",
                chunk_ids,
            )
            conn.execute(
                f"delete from document_chunk where id in ({placeholders})",
                chunk_ids,
            )
            chunk_rows = [(chunk, self._normalized_chunk_metadata(chunk)) for chunk in chunks]
            conn.executemany(
                """
                insert into document_chunk
                (id, doc_id, workspace_id, knowledge_base_id, parent_id, chunk_type, title_path, content, content_markdown,
                 page_start, page_end, token_count, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.doc_id,
                        workspace_id,
                        knowledge_base_id,
                        chunk.parent_id,
                        chunk.chunk_type,
                        chunk.title_path,
                        chunk.content,
                        chunk.content_markdown,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.token_count,
                        json.dumps(metadata, ensure_ascii=False),
                        now,
                    )
                    for chunk, metadata in chunk_rows
                ],
            )
            self._insert_keyword_rows(conn, chunks)

    def reset(self, scope: KnowledgeBaseScope | None = None) -> None:
        scope = scope or self.default_scope()
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        params = [scope.workspace_id, *scope.selected_knowledge_base_ids]
        with self._connect() as conn:
            conn.execute(
                f"delete from document_chunk_fts where id in (select id from document_chunk where workspace_id = ? and knowledge_base_id in ({placeholders}))",
                params,
            )
            conn.execute(
                f"delete from document_chunk where workspace_id = ? and knowledge_base_id in ({placeholders})", params
            )
            conn.execute(f"delete from document where workspace_id = ? and knowledge_base_id in ({placeholders})", params)

    def delete_document(self, doc_id: str, scope: KnowledgeBaseScope | None = None) -> None:
        scope = scope or self.default_scope()
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        params = [doc_id, scope.workspace_id, *scope.selected_knowledge_base_ids]
        with self._connect() as conn:
            exists = conn.execute(
                f"select 1 from document where id = ? and workspace_id = ? and knowledge_base_id in ({placeholders})",
                params,
            ).fetchone()
            if exists is None:
                raise KeyError(doc_id)
            conn.execute(
                f"""
                update knowledge_upload_file
                set document_id = null
                where document_id = ? and workspace_id = ? and knowledge_base_id in ({placeholders})
                """,
                params,
            )
            conn.execute("delete from document_chunk_fts where doc_id = ?", (doc_id,))
            conn.execute("delete from document_chunk where doc_id = ?", (doc_id,))
            conn.execute("delete from document where id = ?", (doc_id,))

    def count_chunks(
        self,
        chunk_types: set[str] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> int:
        scope = scope or self.default_scope()
        params: list[Any] = [scope.workspace_id, *scope.selected_knowledge_base_ids]
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        clauses = ["workspace_id = ?", f"knowledge_base_id in ({placeholders})"]
        if chunk_types:
            type_placeholders = ",".join("?" for _ in chunk_types)
            clauses.append(f"chunk_type in ({type_placeholders})")
            params.extend(sorted(chunk_types))
        with self._connect() as conn:
            row = conn.execute(f"select count(*) from document_chunk where {' and '.join(clauses)}", params).fetchone()
        return int(row[0] if row else 0)

    def list_documents(self, scope: KnowledgeBaseScope | None = None) -> list[dict[str, Any]]:
        scope = scope or self.default_scope()
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                select d.*, count(c.id) as chunks
                from document d
                left join document_chunk c on c.doc_id = d.id
                where d.workspace_id = ? and d.knowledge_base_id in ({placeholders})
                group by d.id
                order by d.updated_at desc
                """,
                (scope.workspace_id, *scope.selected_knowledge_base_ids),
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    def list_chunks(
        self,
        doc_id: str | None = None,
        chunk_types: set[str] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        scope = scope or self.default_scope()
        kb_placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        clauses = ["workspace_id = ?", f"knowledge_base_id in ({kb_placeholders})"]
        params: list[Any] = [scope.workspace_id, *scope.selected_knowledge_base_ids]
        if doc_id:
            clauses.append("doc_id = ?")
            params.append(doc_id)
        elif scope.document_ids:
            doc_placeholders = ",".join("?" for _ in scope.document_ids)
            clauses.append(f"doc_id in ({doc_placeholders})")
            params.extend(scope.document_ids)
        if chunk_types:
            placeholders = ",".join("?" for _ in chunk_types)
            clauses.append(f"chunk_type in ({placeholders})")
            params.extend(sorted(chunk_types))
        where = f" where {' and '.join(clauses)}"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"select * from document_chunk{where} order by created_at, id", params).fetchall()
        return [self._decode_row(row) for row in rows]

    def count_chunks_for_documents(
        self,
        doc_ids: list[str] | tuple[str, ...],
        *,
        chunk_types: set[str] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> dict[str, int]:
        scope = scope or self.default_scope()
        selected_doc_ids = tuple(dict.fromkeys(str(item).strip() for item in doc_ids if str(item).strip()))
        if not selected_doc_ids:
            return {}
        kb_placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        doc_placeholders = ",".join("?" for _ in selected_doc_ids)
        clauses = [
            "workspace_id = ?",
            f"knowledge_base_id in ({kb_placeholders})",
            f"doc_id in ({doc_placeholders})",
        ]
        params: list[Any] = [scope.workspace_id, *scope.selected_knowledge_base_ids, *selected_doc_ids]
        if chunk_types:
            type_placeholders = ",".join("?" for _ in chunk_types)
            clauses.append(f"chunk_type in ({type_placeholders})")
            params.extend(sorted(chunk_types))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                select doc_id, count(*) as chunk_count
                from document_chunk
                where {' and '.join(clauses)}
                group by doc_id
                """,
                params,
            ).fetchall()
        counts = {doc_id: 0 for doc_id in selected_doc_ids}
        counts.update({str(row["doc_id"]): int(row["chunk_count"] or 0) for row in rows})
        return counts

    def list_chunks_for_documents(
        self,
        doc_ids: list[str] | tuple[str, ...],
        *,
        chunk_types: set[str] | None = None,
        scope: KnowledgeBaseScope | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        scope = scope or self.default_scope()
        selected_doc_ids = tuple(dict.fromkeys(str(item).strip() for item in doc_ids if str(item).strip()))
        if not selected_doc_ids:
            return []
        kb_placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        doc_placeholders = ",".join("?" for _ in selected_doc_ids)
        clauses = [
            "workspace_id = ?",
            f"knowledge_base_id in ({kb_placeholders})",
            f"doc_id in ({doc_placeholders})",
        ]
        params: list[Any] = [scope.workspace_id, *scope.selected_knowledge_base_ids, *selected_doc_ids]
        if chunk_types:
            type_placeholders = ",".join("?" for _ in chunk_types)
            clauses.append(f"chunk_type in ({type_placeholders})")
            params.extend(sorted(chunk_types))
        sql = f"select * from document_chunk where {' and '.join(clauses)} order by doc_id, created_at, id"
        if limit is not None:
            sql = f"{sql} limit ?"
            params.append(max(0, int(limit)))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._decode_row(row) for row in rows]

    def get_chunk(self, chunk_id: str, scope: KnowledgeBaseScope | None = None) -> dict[str, Any] | None:
        scope = scope or self.default_scope()
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        clauses = ["id = ?", "workspace_id = ?", f"knowledge_base_id in ({placeholders})"]
        params: list[Any] = [chunk_id, scope.workspace_id, *scope.selected_knowledge_base_ids]
        if scope.document_ids:
            doc_placeholders = ",".join("?" for _ in scope.document_ids)
            clauses.append(f"doc_id in ({doc_placeholders})")
            params.extend(scope.document_ids)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"select * from document_chunk where {' and '.join(clauses)}",
                params,
            ).fetchone()
        if row is None:
            return None
        return self._decode_row(row)

    def get_document(self, doc_id: str, scope: KnowledgeBaseScope | None = None) -> dict[str, Any] | None:
        scope = scope or self.default_scope()
        if scope.document_ids and doc_id not in scope.document_ids:
            return None
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"select * from document where id = ? and workspace_id = ? and knowledge_base_id in ({placeholders})",
                (doc_id, scope.workspace_id, *scope.selected_knowledge_base_ids),
            ).fetchone()
        return self._decode_row(row) if row else None

    def get_document_by_path(
        self,
        storage_path: str,
        scope: KnowledgeBaseScope | None = None,
    ) -> dict[str, Any] | None:
        scope = scope or self.default_scope()
        placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"select * from document where storage_path = ? and workspace_id = ? and knowledge_base_id in ({placeholders})",
                (storage_path, scope.workspace_id, *scope.selected_knowledge_base_ids),
            ).fetchone()
        if row is None:
            return None
        return self._decode_row(row)

    def rebuild_keyword_index(self) -> None:
        with self._connect() as conn:
            self._rebuild_keyword_index(conn)

    def search_keyword_chunks(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []
        scope = scope or self.default_scope()
        kb_placeholders = ",".join("?" for _ in scope.selected_knowledge_base_ids)
        clauses = ["document_chunk_fts match ?", "c.workspace_id = ?", f"c.knowledge_base_id in ({kb_placeholders})"]
        params: list[Any] = [fts_query, scope.workspace_id, *scope.selected_knowledge_base_ids]
        doc_ids = set((filters or {}).get("doc_ids") or scope.document_ids)
        if doc_ids:
            placeholders = ",".join("?" for _ in doc_ids)
            clauses.append(f"f.doc_id in ({placeholders})")
            params.extend(sorted(doc_ids))
        params.append(top_k)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                select
                    f.id,
                    f.doc_id,
                    f.parent_id,
                    f.chunk_type,
                    f.title_path,
                    f.content,
                    f.content_markdown,
                    f.page_start,
                    f.page_end,
                    c.metadata_json,
                    c.workspace_id,
                    c.knowledge_base_id,
                    bm25(document_chunk_fts) as rank
                from document_chunk_fts f
                join document_chunk c on c.id = f.id
                where {' and '.join(clauses)}
                order by rank asc
                limit ?
                """,
                params,
            ).fetchall()
        results = []
        for row in rows:
            item = self._decode_row(row)
            rank = float(item.pop("rank", 0.0) or 0.0)
            item["keyword_score"] = 1.0 / (1.0 + abs(rank))
            results.append(item)
        return results

    def update_enrichment(
        self,
        doc_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str,
        summary: str | None = None,
        keywords: list[str] | None = None,
        suggested_questions: list[str] | None = None,
        error: str | None = None,
        model_ref: str | None = None,
        generated_at: str | None = None,
        source_chunk_ids: list[str] | None = None,
        increment_version: bool = False,
        current_task_id: str | None = None,
        summary_version: int | None = None,
    ) -> dict[str, Any]:
        document = self.get_document(doc_id, scope)
        if document is None:
            raise KeyError(doc_id)
        assignments = ["summary_status = ?", "updated_at = ?"]
        values: list[Any] = [status, datetime.now().isoformat(timespec="seconds")]
        optional = {
            "summary": summary,
            "keywords_json": json.dumps(keywords, ensure_ascii=False) if keywords is not None else None,
            "suggested_questions_json": json.dumps(suggested_questions, ensure_ascii=False)
            if suggested_questions is not None
            else None,
            "summary_error": error,
            "summary_model_ref": model_ref,
            "summary_generated_at": generated_at,
            "summary_source_chunk_ids_json": json.dumps(source_chunk_ids, ensure_ascii=False)
            if source_chunk_ids is not None
            else None,
            "current_enrichment_task_id": current_task_id,
        }
        for column, value in optional.items():
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        if increment_version:
            assignments.append("summary_version = summary_version + 1")
        elif summary_version is not None:
            assignments.append("summary_version = ?")
            values.append(int(summary_version))
        values.extend([doc_id, scope.workspace_id, scope.knowledge_base_id])
        with self._connect() as conn:
            conn.execute(
                f"update document set {', '.join(assignments)} where id = ? and workspace_id = ? and knowledge_base_id = ?",
                values,
            )
        result = self.get_document(doc_id, scope)
        if result is None:
            raise KeyError(doc_id)
        return result

    def create_enrichment_task(
        self,
        doc_id: str,
        scope: KnowledgeBaseScope,
        *,
        provider_ref: str,
        source_chunk_ids: list[str],
    ) -> dict[str, Any]:
        import uuid

        document = self.get_document(doc_id, scope)
        if document is None:
            raise KeyError(doc_id)
        now = datetime.now().isoformat(timespec="seconds")
        task_id = f"enrichment-{uuid.uuid4().hex}"
        with self._connect() as conn:
            row = conn.execute(
                """
                select coalesce(max(version), 0) + 1
                from document_enrichment_task
                where doc_id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (doc_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
            version = int(row[0] if row else 1)
            conn.execute(
                """
                insert into document_enrichment_task(
                    id, doc_id, workspace_id, knowledge_base_id, version, status, provider_ref,
                    error_message, source_chunk_ids_json, started_at, finished_at, created_at
                ) values (?, ?, ?, ?, ?, 'pending', ?, '', ?, null, null, ?)
                """,
                (
                    task_id,
                    doc_id,
                    scope.workspace_id,
                    scope.knowledge_base_id,
                    version,
                    provider_ref,
                    json.dumps(source_chunk_ids, ensure_ascii=False),
                    now,
                ),
            )
            conn.execute(
                """
                update document
                set current_enrichment_task_id = ?, summary_status = 'pending', summary_error = '',
                    summary_version = ?, updated_at = ?
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (task_id, version, now, doc_id, scope.workspace_id, scope.knowledge_base_id),
            )
        return self.get_enrichment_task(task_id, scope)

    def update_enrichment_task(
        self,
        task_id: str,
        scope: KnowledgeBaseScope,
        *,
        status: str,
        error_message: str = "",
    ) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        started_at = now if status == "processing" else None
        finished_at = now if status in {"completed", "failed", "skipped"} else None
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update document_enrichment_task
                set status = ?, error_message = ?,
                    started_at = coalesce(started_at, ?), finished_at = coalesce(?, finished_at)
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (status, error_message, started_at, finished_at, task_id, scope.workspace_id, scope.knowledge_base_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(task_id)
        return self.get_enrichment_task(task_id, scope)

    def get_enrichment_task(self, task_id: str, scope: KnowledgeBaseScope) -> dict[str, Any]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                select * from document_enrichment_task
                where id = ? and workspace_id = ? and knowledge_base_id = ?
                """,
                (task_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        data = dict(row)
        data["source_chunk_ids"] = json.loads(data.pop("source_chunk_ids_json") or "[]")
        return data

    def list_enrichment_tasks(self, doc_id: str, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select * from document_enrichment_task
                where doc_id = ? and workspace_id = ? and knowledge_base_id = ?
                order by version
                """,
                (doc_id, scope.workspace_id, scope.knowledge_base_id),
            ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["source_chunk_ids"] = json.loads(data.pop("source_chunk_ids_json") or "[]")
            result.append(data)
        return result

    def default_scope(self) -> KnowledgeBaseScope:
        return KnowledgeBaseScope(
            workspace_id=self.defaults.workspace_id,
            selected_knowledge_base_ids=(self.defaults.knowledge_base_id,),
            compatibility_default=True,
        )

    def _rebuild_keyword_index(self, conn: sqlite3.Connection) -> None:
        conn.execute("delete from document_chunk_fts")
        conn.execute(
            """
            insert into document_chunk_fts
            (id, doc_id, parent_id, chunk_type, title_path, content, content_markdown, page_start, page_end)
            select id, doc_id, parent_id, chunk_type, title_path, content, content_markdown, page_start, page_end
            from document_chunk
            where chunk_type in ('child', 'table', 'ocr', 'image_ocr', 'image_caption')
            """
        )

    def _insert_keyword_rows(self, conn: sqlite3.Connection, chunks: list[Chunk]) -> None:
        indexable = [chunk for chunk in chunks if chunk.chunk_type in self.KEYWORD_CHUNK_TYPES]
        if not indexable:
            return
        conn.executemany(
            """
            insert into document_chunk_fts
            (id, doc_id, parent_id, chunk_type, title_path, content, content_markdown, page_start, page_end)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id,
                    chunk.doc_id,
                    chunk.parent_id,
                    chunk.chunk_type,
                    chunk.title_path,
                    chunk.content,
                    chunk.content_markdown,
                    chunk.page_start,
                    chunk.page_end,
                )
                for chunk in indexable
            ],
        )

    def _build_fts_query(self, query: str) -> str:
        tokens = re.findall(r"[\w.\-:/]+", query, flags=re.UNICODE)
        normalized = []
        for token in tokens:
            token = token.strip("-_:/.")
            if len(token) >= 2:
                normalized.append(token.replace('"', '""'))
        return " OR ".join(f'"{token}"' for token in dict.fromkeys(normalized))

    def _normalized_chunk_metadata(self, chunk: Chunk) -> dict[str, Any]:
        metadata = dict(chunk.metadata)
        metadata.setdefault("processing_version", PROCESSING_VERSION)
        metadata.setdefault("size_unit", "chars")
        metadata.setdefault("strategy", self._default_chunk_strategy(chunk))
        if chunk.chunk_type in {"image_ocr", "image_caption", "ocr"}:
            metadata.setdefault("generated_evidence", chunk.chunk_type in {"image_ocr", "image_caption"})
        return metadata

    def _default_chunk_strategy(self, chunk: Chunk) -> str:
        if chunk.chunk_type in {"image_ocr", "image_caption"}:
            return chunk.chunk_type
        if chunk.chunk_type == "ocr":
            return "ocr"
        if chunk.chunk_type == "table":
            return "table"
        return "legacy"

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if "metadata_json" in data:
            data["metadata_json"] = json.loads(data["metadata_json"] or "{}")
        for field_name in ("keywords_json", "suggested_questions_json", "summary_source_chunk_ids_json"):
            if field_name in data:
                data[field_name] = json.loads(data[field_name] or "[]")
        return data

    def _assert_active_knowledge_base(
        self,
        conn: sqlite3.Connection,
        workspace_id: str,
        knowledge_base_id: str,
    ) -> None:
        row = conn.execute(
            "select 1 from knowledge_base where id = ? and workspace_id = ? and status = 'active'",
            (knowledge_base_id, workspace_id),
        ).fetchone()
        if row is None:
            raise ValueError("Knowledge base does not exist, is archived, or belongs to another workspace")
