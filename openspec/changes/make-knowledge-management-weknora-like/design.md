## Context

Bee already has a multi-knowledge-base domain, scoped documents, scoped retrieval, and a basic WeKnora-inspired catalog. The current knowledge page still treats upload as a direct action: choosing files immediately posts each file to `/documents/upload`, and the backend synchronously saves, parses, chunks, embeds, indexes, and returns a result. That is useful for a small demo, but it does not match the operational shape shown in Weknora screenshots:

```text
select files -> pending list -> confirm parsing/index settings -> process batch -> monitor document states
```

The project constraints remain:

- Keep Bee branding and the existing Next.js/FastAPI stack.
- Do not copy WeKnora source code, logo, or brand copy.
- Preserve `KnowledgeBaseScope`; no upload, task, document, or chunk may float outside an active KB.
- Do not upload local files during implementation or verification unless the user explicitly asks.
- Keep destructive reset out of the normal UI.

## Goals / Non-Goals

**Goals:**

- Make the knowledge-base UI behaviorally comparable to Weknora for creation, upload confirmation, document management, and processing status.
- Turn upload into a staged, auditable workflow with durable backend batch/task state.
- Support per-batch parsing/indexing choices while showing requested and effective provider behavior honestly.
- Provide dense document navigation: search, filter, view mode, selected actions, status, and retry.
- Preserve current default-KB compatibility for existing clients.

**Non-Goals:**

- Do not implement FAQ, Wiki, external connector sync, sharing, RBAC, or membership management.
- Do not implement real web-page import or online document editing in this change; menu entries can be disabled or marked unavailable.
- Do not introduce a full distributed queue such as Celery unless the existing process cannot safely represent the lifecycle.
- Do not provide a browser global data purge/reset button.
- Do not require data migration from any old upload task shape.

## Decisions

### 1. Define "Weknora-like" as interaction structure, not visual cloning

Bee will mirror these product behaviors:

```text
Knowledge catalog
  - left scope/filter rail
  - compact cards
  - create entry

Create KB
  - modal/drawer with left config navigation
  - base info, type, index strategy, model/parser/chunk settings
  - unsupported features visible but not silently enabled

KB documents
  - searchable/filterable toolbar
  - upload action menu
  - grid/list mode
  - status-rich document cards

Upload
  - pending files before transfer
  - confirmation dialog
  - per-batch config
  - task monitoring and retry
```

Visual styling should stay close to the existing Bee shell: pale navigation, green status accents, compact cards, low-radius controls, and existing CSS variables.

Alternative considered: copy Weknora screens pixel-for-pixel. Rejected because it risks brand/source copying and ignores Bee's existing layout, routing, and design system.

### 2. Persist upload batches and file tasks in backend metadata

Add durable scoped task state to SQLite, for example:

```text
knowledge_upload_batch(
  id, workspace_id, knowledge_base_id, status,
  settings_json, created_at, updated_at, confirmed_at, completed_at,
  error
)

knowledge_upload_file(
  id, batch_id, workspace_id, knowledge_base_id,
  original_name, relative_path, storage_path, size,
  status, document_id, chunks, error,
  created_at, updated_at
)
```

Status values should cover at least:

```text
batch: draft -> uploading -> ready_to_process -> processing -> completed | partial_failed | failed | canceled
file: pending -> uploaded -> parsing -> indexed -> enrichment_pending | completed | failed | canceled
```

Rationale:

- A pending/processing upload should survive refresh.
- Backend can report truth instead of relying on transient frontend rows.
- Batch/task rows give tests a stable contract for partial failure and retry.

Alternative considered: keep frontend-only upload task state. Rejected because it cannot support Weknora-like confirmation and durable task monitoring.

### 3. Split file transfer from parse/index processing

Use staged endpoints rather than making file selection immediately index:

```text
POST /knowledge-bases/{kb_id}/upload-batches
POST /knowledge-bases/{kb_id}/upload-batches/{batch_id}/files
PATCH /knowledge-bases/{kb_id}/upload-batches/{batch_id}/settings
POST /knowledge-bases/{kb_id}/upload-batches/{batch_id}/confirm
GET /knowledge-bases/{kb_id}/upload-batches/{batch_id}
POST /knowledge-bases/{kb_id}/upload-batches/{batch_id}/files/{file_id}/retry
POST /knowledge-bases/{kb_id}/upload-batches/{batch_id}/cancel
```

The existing `/documents/upload` path can remain as a compatibility shortcut. New UI must use the staged path.

Processing can initially run in-process after confirm, but the API contract must behave like an async task: confirmation returns quickly with task status, and the UI polls. If processing is still synchronous internally for the first implementation, the backend must still persist intermediate states before and after each major phase.

Alternative considered: one giant multipart batch request. Rejected because it does not provide pending-file review, per-file retry, or clear progress once parsing begins.

### 4. Treat parsing/indexing options as requested/effective config

The upload confirmation dialog should expose a bounded subset of Weknora-like options:

- parser engine: current effective parser, initially read-only if only one parser exists
- chunk size, overlap, parent-child mode if supported
- dense retrieval enabled
- keyword retrieval enabled
- graph extraction enabled if configured
- document enrichment/question generation enabled if configured
- OCR/multimodal/audio options visible only when supported or shown disabled

Backend stores requested settings with the batch and computes effective settings from runtime capability. The UI must not imply an unsupported option will run.

Alternative considered: expose every Weknora option immediately. Rejected because this project does not yet support FAQ/Wiki, multimodal parsing, audio, or all provider overrides.

### 5. Keep document workspace filters API-backed

The document workspace should not fetch all documents and filter everything client-side once a KB grows. Add query parameters to the documents endpoint or add a scoped document search endpoint:

```text
knowledge_base_id
q
tag
file_type
status
source
created_from
created_to
view_mode is client-only
```

The initial implementation may return a simple list if pagination is not yet present, but the contract should leave space for server-side pagination.

Alternative considered: client-only filters. Acceptable for small data, but rejected as the target behavior because Weknora-like document workspaces are built for repeated operation over many files.

### 6. Use component boundaries before adding a second styling system

Break the large knowledge page into focused local components while keeping request logic in `frontend/app/lib/api.ts`:

```text
KnowledgeCatalog
KnowledgeBaseCreateWizard
KnowledgeBaseDetailShell
DocumentToolbar
DocumentGrid
DocumentList
UploadActionMenu
PendingUploadDialog
UploadBatchMonitor
KnowledgeBaseSettingsDialog
```

Styling remains in `globals.css` unless the project adopts a component style system in a separate migration.

## Risks / Trade-offs

- Task tables add schema and repository complexity -> keep the lifecycle small and model only upload/parse/index/enrichment states needed by the UI.
- In-process background work may still block under large PDFs -> make the API async-shaped now, so a real worker can replace the executor later.
- Exposing unsupported Weknora options can frustrate users -> show them disabled with concrete status, or hide them unless they help explain the product path.
- Backwards-compatible `/documents/upload` may diverge from staged upload -> keep it as a simple shortcut into the same service layer where possible.
- More document filters can create slow SQLite queries -> add targeted indexes and defer full pagination if not required for first implementation.
- Uploading to external providers has data-safety implications -> the UI confirmation must make processing explicit, and tests must not upload real private files.

## Migration Plan

1. Add backend batch/task schema initialization and repository tests.
2. Add staged upload routes while preserving existing upload and document routes.
3. Wire processing through existing parser, chunker, vector store, enrichment, and KB scope logic.
4. Refactor the knowledge page into components and switch upload UI to staged batch flow.
5. Add document workspace filters and grid/list modes.
6. Update docs and run focused backend/frontend validation.

Rollback strategy:

- Hide the staged upload entry and fall back to the existing `/documents/upload` path.
- Keep task tables inert if UI is rolled back; they do not change retrieval behavior.
- Do not delete uploaded sources or indexed documents as part of rollback.

## Open Questions

- Should upload confirmation default to enrichment enabled or disabled when an external LLM provider is configured?
- Should grid/list view preference be global, per user, or local-storage only for this phase?
- Should unsupported "导入网页" and "在线编辑" entries be shown disabled now, or omitted until their backend exists?
- Should batch processing start automatically after the final file upload when the user has already confirmed settings, or always require a separate confirm button?
