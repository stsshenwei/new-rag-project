## Why

The multi-knowledge-base domain is now present, but the knowledge page still feels like a thin document list with immediate upload side effects. Users expect a WeKnora-like management console where they can create a knowledge base, review files before upload, choose parsing/indexing options, monitor background processing, and filter a dense document workspace without accidentally sending files to providers.

This change defines how far Bee should mirror WeKnora: adopt the knowledge-management information architecture and operational flow, while keeping Bee branding, the existing Next.js/FastAPI stack, and the current multi-KB ownership model.

## What Changes

- Add a WeKnora-style knowledge-base creation wizard with a left configuration rail, base information, knowledge-base type selection, index strategy, parser/chunk settings, model/provider visibility, and advanced options.
- Replace direct upload-as-ingest with a staged upload workflow: select files or folders, show a pending-file list, let the user review upload settings, then explicitly confirm upload and processing.
- Add a document management workspace for a selected KB with search, tag/type/status/source/time filters, grid/list display modes, compact document cards, bulk selection, and per-document actions.
- Add an upload action menu matching the expected information architecture: upload documents, upload folders, import webpage, and online editing. Unsupported modes may be visible as disabled or "coming later" entries if the backend is not ready.
- Add batch/task semantics to the backend so upload, parse, indexing, enrichment, and failure/retry states can be tracked independently from the HTTP file-transfer request.
- Keep the current multi-KB scope rules: every upload batch, task, document, chunk, and retry remains bound to exactly one active knowledge base.
- Preserve Bee branding and design system. Do not copy WeKnora logos, source code, brand text, or implementation-specific component structure.
- Do not upload any existing local files as part of this change.
- **BREAKING** for the knowledge UI only: selecting files no longer immediately indexes them; users must confirm the pending upload batch.

## Capabilities

### New Capabilities

- `weknora-like-knowledge-creation`: Knowledge-base creation and settings flows with a WeKnora-like configuration structure adapted to Bee.
- `weknora-like-document-workspace`: Searchable, filterable, mode-switchable document management workspace for a selected knowledge base.
- `staged-knowledge-upload`: Pending upload queue, upload confirmation dialog, per-batch parsing/indexing options, and explicit processing start.
- `knowledge-processing-tasks`: Backend-visible upload/parse/index/enrichment task lifecycle for batches and files scoped to a single KB.

### Modified Capabilities

- None. Existing main specs have not yet been archived; this change introduces new delta specs and depends on the completed `add-multi-knowledge-base-domain` behavior.

## Impact

- Frontend: `frontend/app/knowledge/page.tsx`, supporting components under `frontend/app/components/`, `frontend/app/lib/api.ts`, `frontend/app/lib/types.ts`, and `frontend/app/globals.css`.
- Backend: FastAPI upload/document routes, schemas, `RAGService` upload and ingest orchestration, document repository metadata, and task/batch persistence in SQLite.
- Data model: add durable upload batch and file task records, or equivalent final-schema tables, scoped by `workspace_id` and `knowledge_base_id`.
- API: add staged upload/confirm/task-status endpoints while preserving backwards compatibility for existing upload callers where practical.
- Docs: update frontend UI and backend RAG pipeline design docs to describe staged upload, provider-safety expectations, task lifecycle, and unsupported WeKnora-like menu items.
- Validation: add focused backend tests for task state and KB isolation, frontend tests/build for the knowledge page, and manual smoke coverage for creation, pending upload, confirm/cancel, filters, status refresh, and disabled future import modes.
