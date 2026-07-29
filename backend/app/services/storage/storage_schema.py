from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


METADATA_SCHEMA_VERSION = "20260715_adaptive_document_processing_v2"
EVALUATION_SCHEMA_VERSION = "20260713_evaluation_final_v1"


class StorageResetRequired(RuntimeError):
    """Raised when persisted data cannot be opened by the final schema."""


@dataclass(frozen=True)
class DefaultKnowledgeBaseSettings:
    workspace_id: str = "default-workspace"
    workspace_name: str = "默认工作空间"
    knowledge_base_id: str = "default-knowledge-base"
    knowledge_base_name: str = "默认知识库"

    def __post_init__(self) -> None:
        for field_name in ("workspace_id", "workspace_name", "knowledge_base_id", "knowledge_base_name"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} cannot be empty")


def initialize_metadata_database(
    db_path: Path | str,
    defaults: DefaultKnowledgeBaseSettings | None = None,
) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("pragma foreign_keys = on")
        conn.execute("begin immediate")
        _ensure_empty_or_version(conn, METADATA_SCHEMA_VERSION, "metadata")
        if not _table_exists(conn, "storage_schema"):
            _create_metadata_schema(conn, defaults or DefaultKnowledgeBaseSettings())
        else:
            _validate_required_tables(conn, _METADATA_TABLES, "metadata")
            _ensure_processing_span_schema(conn)
            _ensure_processing_task_schema(conn)
            _ensure_default_entities(conn, defaults or DefaultKnowledgeBaseSettings())
        _ensure_processing_task_schema(conn)
        _ensure_agent_runtime_span_schema(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_evaluation_database(db_path: Path | str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("pragma foreign_keys = on")
        conn.execute("begin immediate")
        _ensure_empty_or_version(conn, EVALUATION_SCHEMA_VERSION, "evaluation")
        if not _table_exists(conn, "storage_schema"):
            _create_evaluation_schema(conn)
        else:
            _validate_required_tables(conn, _EVALUATION_TABLES, "evaluation")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inspect_schema(db_path: Path | str, expected_version: str) -> dict[str, object]:
    path = Path(db_path)
    if not path.exists():
        return {"exists": False, "empty": True, "version": None, "reset_required": False}
    conn = sqlite3.connect(path)
    try:
        tables = _user_tables(conn)
        version = None
        if "storage_schema" in tables:
            row = conn.execute("select version from storage_schema where component = 'primary'").fetchone()
            version = str(row[0]) if row else None
        return {
            "exists": True,
            "empty": not tables,
            "version": version,
            "reset_required": bool(tables) and version != expected_version,
        }
    finally:
        conn.close()


def _ensure_empty_or_version(conn: sqlite3.Connection, expected_version: str, label: str) -> None:
    tables = _user_tables(conn)
    if not tables:
        return
    if "storage_schema" not in tables:
        raise StorageResetRequired(
            f"{label} storage uses a legacy schema; run the clean-rebuild CLI before starting the service"
        )
    row = conn.execute("select version from storage_schema where component = 'primary'").fetchone()
    actual = str(row[0]) if row else ""
    if actual != expected_version:
        raise StorageResetRequired(
            f"{label} storage schema {actual or '<missing>'!r} is incompatible with {expected_version!r}; "
            "run the clean-rebuild CLI"
        )


def _create_metadata_schema(conn: sqlite3.Connection, defaults: DefaultKnowledgeBaseSettings) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.executescript(
        """
        create table storage_schema (
            component text primary key,
            version text not null,
            initialized_at text not null
        );

        create table workspace (
            id text primary key,
            name text not null,
            description text not null default '',
            status text not null default 'active' check(status in ('active', 'archived')),
            created_at text not null,
            updated_at text not null
        );

        create table knowledge_base (
            id text primary key,
            workspace_id text not null,
            name text not null collate nocase,
            description text not null default '',
            type text not null default 'document' check(type = 'document'),
            status text not null default 'active' check(status in ('active', 'archived')),
            indexing_strategy_json text not null default '{}',
            provider_config_json text not null default '{}',
            reset_required integer not null default 0 check(reset_required in (0, 1)),
            created_at text not null,
            updated_at text not null,
            unique(workspace_id, id),
            unique(workspace_id, name),
            foreign key(workspace_id) references workspace(id)
        );

        create table document (
            id text primary key,
            workspace_id text not null,
            knowledge_base_id text not null,
            name text not null,
            file_type text not null,
            storage_path text not null,
            parse_status text not null,
            created_at text not null,
            updated_at text not null,
            metadata_json text not null default '{}',
            summary text not null default '',
            keywords_json text not null default '[]',
            suggested_questions_json text not null default '[]',
            summary_status text not null default 'none',
            summary_error text not null default '',
            summary_model_ref text not null default '',
            summary_generated_at text,
            summary_version integer not null default 0,
            summary_source_chunk_ids_json text not null default '[]',
            current_enrichment_task_id text,
            unique(workspace_id, knowledge_base_id, id),
            foreign key(workspace_id, knowledge_base_id)
                references knowledge_base(workspace_id, id)
        );

        create table document_chunk (
            id text primary key,
            doc_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            parent_id text,
            chunk_type text not null,
            title_path text not null,
            content text not null,
            content_markdown text not null,
            page_start integer,
            page_end integer,
            token_count integer not null,
            metadata_json text not null default '{}',
            created_at text not null,
            unique(workspace_id, knowledge_base_id, id),
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table parse_task (
            id text primary key,
            doc_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            status text not null,
            error_message text not null default '',
            started_at text,
            finished_at text,
            created_at text not null,
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table document_image_resource (
            id text primary key,
            workspace_id text not null,
            knowledge_base_id text not null,
            doc_id text not null,
            storage_key text not null,
            storage_provider text not null default 'local',
            source_type text not null,
            page_number integer,
            mime_type text not null,
            width integer,
            height integer,
            metadata_json text not null default '{}',
            created_at text not null,
            unique(workspace_id, knowledge_base_id, id),
            unique(workspace_id, knowledge_base_id, storage_key),
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table document_image_operation (
            id text primary key,
            image_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            doc_id text not null,
            operation_type text not null check(operation_type in ('ocr', 'caption')),
            status text not null check(status in ('pending', 'processing', 'completed', 'failed', 'canceled')),
            provider_ref text not null default '',
            result_chunk_id text,
            error_message text not null default '',
            attempt integer not null default 0,
            created_at text not null,
            updated_at text not null,
            unique(workspace_id, knowledge_base_id, image_id, operation_type),
            foreign key(workspace_id, knowledge_base_id, image_id)
                references document_image_resource(workspace_id, knowledge_base_id, id) on delete cascade,
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table document_enrichment_task (
            id text primary key,
            doc_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            version integer not null,
            status text not null,
            provider_ref text not null default '',
            error_message text not null default '',
            source_chunk_ids_json text not null default '[]',
            started_at text,
            finished_at text,
            created_at text not null,
            unique(workspace_id, knowledge_base_id, doc_id, version),
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table knowledge_processing_spans (
            id integer primary key autoincrement,
            knowledge_id text not null,
            attempt integer not null,
            span_id text not null unique,
            parent_span_id text,
            name text not null,
            kind text not null,
            status text not null,
            input_json text not null default '{}',
            output_json text not null default '{}',
            metadata_json text not null default '{}',
            error_code text not null default '',
            error_message text not null default '',
            error_detail text not null default '',
            started_at text,
            finished_at text,
            duration_ms integer not null default 0,
            created_at text not null,
            updated_at text not null,
            unique(knowledge_id, attempt, parent_span_id, name, kind)
        );

        create table document_processing_task (
            id text primary key,
            task_type text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            document_id text not null default '',
            upload_batch_id text not null default '',
            upload_file_id text not null default '',
            status text not null check(status in (
                'pending', 'retrying', 'processing', 'completed', 'failed', 'canceled', 'dead_lettered'
            )),
            payload_json text not null default '{}',
            attempt integer not null default 0,
            max_attempts integer not null default 3,
            next_run_at text not null,
            lease_owner text not null default '',
            lease_expires_at text,
            last_error_code text not null default '',
            last_error_message text not null default '',
            trace_id text not null default '',
            created_at text not null,
            updated_at text not null,
            started_at text,
            finished_at text,
            unique(workspace_id, knowledge_base_id, task_type, document_id, upload_batch_id, upload_file_id)
        );

        create table document_processing_dead_letter (
            id text primary key,
            task_id text not null,
            task_type text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            document_id text not null default '',
            upload_batch_id text not null default '',
            upload_file_id text not null default '',
            payload_json text not null default '{}',
            error_code text not null default '',
            error_message text not null default '',
            attempt integer not null default 0,
            trace_id text not null default '',
            created_at text not null
        );

        create table kg_extraction_task (
            id text primary key,
            doc_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            status text not null,
            error_message text,
            extractor_version text not null,
            parent_chunk_count integer not null default 0,
            metadata_json text not null default '{}',
            started_at text,
            finished_at text,
            created_at text not null,
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table entity_mention (
            id text primary key,
            workspace_id text not null,
            knowledge_base_id text not null,
            entity_id text not null,
            entity_type text not null,
            entity_name text not null,
            doc_id text not null,
            chunk_id text not null,
            parent_id text,
            page_start integer,
            page_end integer,
            mention_text text not null,
            confidence real not null,
            aliases_json text not null default '[]',
            description text not null default '',
            metadata_json text not null default '{}',
            created_at text not null,
            foreign key(workspace_id, knowledge_base_id, doc_id)
                references document(workspace_id, knowledge_base_id, id) on delete cascade,
            foreign key(workspace_id, knowledge_base_id, chunk_id)
                references document_chunk(workspace_id, knowledge_base_id, id) on delete cascade
        );

        create table graph_community_summary (
            id text primary key,
            workspace_id text not null,
            knowledge_base_id text not null,
            community_id text not null,
            summary text not null,
            entity_ids_json text not null default '[]',
            source_chunk_ids_json text not null default '[]',
            confidence real not null,
            metadata_json text not null default '{}',
            created_at text not null,
            updated_at text not null,
            unique(workspace_id, knowledge_base_id, community_id),
            foreign key(workspace_id, knowledge_base_id)
                references knowledge_base(workspace_id, id) on delete cascade
        );

        create table query_log (
            id text primary key,
            workspace_id text not null,
            knowledge_base_ids_json text not null,
            question text not null,
            status text not null,
            query_type text not null default '',
            tool_calls_json text not null default '[]',
            citation_chunk_ids_json text not null default '[]',
            response_metadata_json text not null default '{}',
            error_message text not null default '',
            created_at text not null,
            finished_at text
        );

        create table answer_feedback (
            id text primary key,
            query_log_id text,
            workspace_id text not null,
            knowledge_base_id text not null,
            rating text not null default '',
            correction text not null default '',
            source_chunk_ids_json text not null default '[]',
            metadata_json text not null default '{}',
            created_at text not null,
            foreign key(query_log_id) references query_log(id) on delete set null,
            foreign key(workspace_id, knowledge_base_id)
                references knowledge_base(workspace_id, id)
        );

        create table knowledge_upload_batch (
            id text primary key,
            workspace_id text not null,
            knowledge_base_id text not null,
            status text not null check(status in (
                'draft', 'uploading', 'ready_to_process', 'processing',
                'completed', 'partial_failed', 'failed', 'canceled'
            )),
            settings_json text not null default '{}',
            error_message text not null default '',
            created_at text not null,
            updated_at text not null,
            confirmed_at text,
            completed_at text,
            unique(workspace_id, knowledge_base_id, id),
            foreign key(workspace_id, knowledge_base_id)
                references knowledge_base(workspace_id, id) on delete cascade
        );

        create table knowledge_upload_file (
            id text primary key,
            batch_id text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            original_name text not null,
            relative_path text not null,
            storage_path text not null default '',
            size integer not null default 0,
            status text not null check(status in (
                'pending', 'uploaded', 'parsing', 'indexed',
                'enrichment_pending', 'completed', 'failed', 'canceled'
            )),
            document_id text,
            chunks integer not null default 0,
            error_message text not null default '',
            phases_json text not null default '[]',
            warnings_json text not null default '[]',
            errors_json text not null default '[]',
            retry_eligible integer not null default 0 check(retry_eligible in (0, 1)),
            created_at text not null,
            updated_at text not null,
            foreign key(workspace_id, knowledge_base_id, batch_id)
                references knowledge_upload_batch(workspace_id, knowledge_base_id, id) on delete cascade,
            foreign key(workspace_id, knowledge_base_id, document_id)
                references document(workspace_id, knowledge_base_id, id) on delete set null
        );

        create virtual table document_chunk_fts using fts5(
            id unindexed,
            doc_id unindexed,
            parent_id unindexed,
            chunk_type unindexed,
            title_path,
            content,
            content_markdown,
            page_start unindexed,
            page_end unindexed,
            tokenize = 'unicode61'
        );

        create index idx_knowledge_base_workspace_status on knowledge_base(workspace_id, status, updated_at);
        create index idx_document_kb_updated on document(workspace_id, knowledge_base_id, updated_at);
        create index idx_document_kb_status on document(workspace_id, knowledge_base_id, parse_status);
        create index idx_document_chunk_kb_doc on document_chunk(workspace_id, knowledge_base_id, doc_id, chunk_type);
        create index idx_parse_task_kb_status on parse_task(workspace_id, knowledge_base_id, status);
        create index idx_image_resource_kb_doc on document_image_resource(workspace_id, knowledge_base_id, doc_id, page_number);
        create index idx_image_operation_kb_status on document_image_operation(workspace_id, knowledge_base_id, status, updated_at);
        create index idx_enrichment_task_kb_doc on document_enrichment_task(workspace_id, knowledge_base_id, doc_id, version);
        create index idx_spans_knowledge_attempt on knowledge_processing_spans(knowledge_id, attempt);
        create index idx_spans_parent on knowledge_processing_spans(parent_span_id);
        create index idx_processing_task_runnable on document_processing_task(status, next_run_at, lease_expires_at);
        create index idx_processing_task_scope_doc on document_processing_task(workspace_id, knowledge_base_id, document_id, status);
        create index idx_processing_task_upload on document_processing_task(workspace_id, knowledge_base_id, upload_batch_id, upload_file_id);
        create index idx_processing_dead_letter_scope on document_processing_dead_letter(workspace_id, knowledge_base_id, created_at);
        create index idx_kg_task_kb_doc on kg_extraction_task(workspace_id, knowledge_base_id, doc_id);
        create index idx_entity_mention_kb_entity on entity_mention(workspace_id, knowledge_base_id, entity_id);
        create index idx_graph_summary_kb on graph_community_summary(workspace_id, knowledge_base_id, updated_at);
        create index idx_query_log_scope_created on query_log(workspace_id, created_at);
        create index idx_answer_feedback_kb_created on answer_feedback(workspace_id, knowledge_base_id, created_at);
        create index idx_upload_batch_kb_status on knowledge_upload_batch(workspace_id, knowledge_base_id, status, updated_at);
        create index idx_upload_file_batch_status on knowledge_upload_file(workspace_id, knowledge_base_id, batch_id, status);

        create trigger trg_document_ownership_update
        before update of workspace_id, knowledge_base_id on document
        begin select raise(abort, 'document ownership is immutable'); end;

        create trigger trg_chunk_ownership_update
        before update of doc_id, workspace_id, knowledge_base_id on document_chunk
        begin select raise(abort, 'chunk ownership is immutable'); end;

        create trigger trg_image_resource_ownership_update
        before update of doc_id, workspace_id, knowledge_base_id on document_image_resource
        begin select raise(abort, 'image resource ownership is immutable'); end;

        create trigger trg_image_operation_ownership_update
        before update of image_id, doc_id, workspace_id, knowledge_base_id on document_image_operation
        begin select raise(abort, 'image operation ownership is immutable'); end;
        """
    )
    conn.execute(
        "insert into storage_schema(component, version, initialized_at) values ('primary', ?, ?)",
        (METADATA_SCHEMA_VERSION, now),
    )
    _ensure_default_entities(conn, defaults, now=now)


def _create_evaluation_schema(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.executescript(
        """
        create table storage_schema (
            component text primary key,
            version text not null,
            initialized_at text not null
        );
        create table eval_run (
            id text primary key,
            dataset_id text not null,
            dataset_version text not null,
            dataset_path text not null,
            status text not null,
            started_at text not null,
            finished_at text,
            created_at text not null,
            updated_at text not null,
            config_snapshot text not null,
            aggregate_scores text not null,
            report_paths text not null,
            error_message text not null,
            knowledge_base_ids_json text not null default '[]'
        );
        create table eval_result (
            id text primary key,
            run_id text not null,
            case_id text not null,
            status text not null,
            question text not null,
            query_type text not null,
            tags text not null,
            case_snapshot text not null,
            answer text not null,
            response_snapshot text not null,
            evidence_snapshot text not null,
            metric_scores text not null,
            latency_ms real not null,
            error_message text not null,
            created_at text not null,
            knowledge_base_ids_json text not null default '[]',
            foreign key(run_id) references eval_run(id) on delete cascade
        );
        create index idx_eval_run_status_updated on eval_run(status, updated_at);
        create index idx_eval_result_run_case on eval_result(run_id, case_id);
        """
    )
    conn.execute(
        "insert into storage_schema(component, version, initialized_at) values ('primary', ?, ?)",
        (EVALUATION_SCHEMA_VERSION, now),
    )


def _ensure_default_entities(
    conn: sqlite3.Connection,
    settings: DefaultKnowledgeBaseSettings,
    now: str | None = None,
) -> None:
    now = now or datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        insert or ignore into workspace(id, name, description, status, created_at, updated_at)
        values (?, ?, '', 'active', ?, ?)
        """,
        (settings.workspace_id, settings.workspace_name, now, now),
    )
    existing = conn.execute(
        "select workspace_id from knowledge_base where id = ?", (settings.knowledge_base_id,)
    ).fetchone()
    if existing is not None and str(existing[0]) != settings.workspace_id:
        raise StorageResetRequired("Configured default knowledge base belongs to another workspace")
    conn.execute(
        """
        insert or ignore into knowledge_base(
            id, workspace_id, name, description, type, status,
            indexing_strategy_json, provider_config_json, reset_required, created_at, updated_at
        ) values (?, ?, ?, '', 'document', 'active', ?, ?, 0, ?, ?)
        """,
        (
            settings.knowledge_base_id,
            settings.workspace_id,
            settings.knowledge_base_name,
            json.dumps({"dense_enabled": True, "keyword_enabled": True, "graph_enabled": False}),
            json.dumps({"requested": {}, "effective": {}, "inactive_overrides": []}),
            now,
            now,
        ),
    )


def _validate_required_tables(conn: sqlite3.Connection, required: set[str], label: str) -> None:
    missing = sorted(required - _user_tables(conn))
    if missing:
        raise StorageResetRequired(f"{label} storage is missing final-schema tables {missing}; run clean-rebuild")


def _ensure_processing_span_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists knowledge_processing_spans (
            id integer primary key autoincrement,
            knowledge_id text not null,
            attempt integer not null,
            span_id text not null unique,
            parent_span_id text,
            name text not null,
            kind text not null,
            status text not null,
            input_json text not null default '{}',
            output_json text not null default '{}',
            metadata_json text not null default '{}',
            error_code text not null default '',
            error_message text not null default '',
            error_detail text not null default '',
            started_at text,
            finished_at text,
            duration_ms integer not null default 0,
            created_at text not null,
            updated_at text not null,
            unique(knowledge_id, attempt, parent_span_id, name, kind)
        );
        create index if not exists idx_spans_knowledge_attempt on knowledge_processing_spans(knowledge_id, attempt);
        create index if not exists idx_spans_parent on knowledge_processing_spans(parent_span_id);
        """
    )


def _ensure_processing_task_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists document_processing_task (
            id text primary key,
            task_type text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            document_id text not null default '',
            upload_batch_id text not null default '',
            upload_file_id text not null default '',
            status text not null check(status in (
                'pending', 'retrying', 'processing', 'completed', 'failed', 'canceled', 'dead_lettered'
            )),
            payload_json text not null default '{}',
            attempt integer not null default 0,
            max_attempts integer not null default 3,
            next_run_at text not null,
            lease_owner text not null default '',
            lease_expires_at text,
            last_error_code text not null default '',
            last_error_message text not null default '',
            trace_id text not null default '',
            created_at text not null,
            updated_at text not null,
            started_at text,
            finished_at text,
            unique(workspace_id, knowledge_base_id, task_type, document_id, upload_batch_id, upload_file_id)
        );
        create table if not exists document_processing_dead_letter (
            id text primary key,
            task_id text not null,
            task_type text not null,
            workspace_id text not null,
            knowledge_base_id text not null,
            document_id text not null default '',
            upload_batch_id text not null default '',
            upload_file_id text not null default '',
            payload_json text not null default '{}',
            error_code text not null default '',
            error_message text not null default '',
            attempt integer not null default 0,
            trace_id text not null default '',
            created_at text not null
        );
        create index if not exists idx_processing_task_runnable on document_processing_task(status, next_run_at, lease_expires_at);
        create index if not exists idx_processing_task_scope_doc on document_processing_task(workspace_id, knowledge_base_id, document_id, status);
        create index if not exists idx_processing_task_upload on document_processing_task(workspace_id, knowledge_base_id, upload_batch_id, upload_file_id);
        create index if not exists idx_processing_dead_letter_scope on document_processing_dead_letter(workspace_id, knowledge_base_id, created_at);
        """
    )


def _ensure_agent_runtime_span_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists agent_runtime_spans (
            id integer primary key autoincrement,
            run_id text not null,
            span_id text not null unique,
            parent_span_id text not null default '',
            name text not null,
            kind text not null,
            status text not null,
            input_json text not null default '{}',
            output_json text not null default '{}',
            metadata_json text not null default '{}',
            error_message text not null default '',
            started_at text,
            finished_at text,
            duration_ms integer not null default 0,
            created_at text not null,
            updated_at text not null
        );
        create index if not exists idx_agent_runtime_spans_run on agent_runtime_spans(run_id);
        create index if not exists idx_agent_runtime_spans_parent on agent_runtime_spans(parent_span_id);
        """
    )


def _user_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "select name from sqlite_master where type = 'table' and name not like 'sqlite_%'"
        ).fetchall()
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return table in _user_tables(conn)


_METADATA_TABLES = {
    "storage_schema",
    "workspace",
    "knowledge_base",
    "document",
    "document_chunk",
    "document_chunk_fts",
    "parse_task",
    "document_image_resource",
    "document_image_operation",
    "document_enrichment_task",
    "kg_extraction_task",
    "entity_mention",
    "graph_community_summary",
    "query_log",
    "answer_feedback",
    "knowledge_upload_batch",
    "knowledge_upload_file",
    "document_processing_task",
    "document_processing_dead_letter",
}

_EVALUATION_TABLES = {"storage_schema", "eval_run", "eval_result"}
