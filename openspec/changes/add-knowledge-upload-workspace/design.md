## Context

The application already has a FastAPI backend and a Next.js knowledge page. The current upload path is synchronous and single-file oriented:

```text
frontend knowledge page
  -> POST /documents/upload with one file
  -> RAGService.save_uploaded_document()
  -> save under backend/data/uploads/
  -> parse_and_index_document()
  -> SQLite document/document_chunk
  -> Milvus vector index
```

This flow reuses the right parsing and indexing boundaries, but it does not support importing a folder hierarchy or showing useful progress for a multi-file knowledge pack. Browser folder selection can provide `File.webkitRelativePath`, which lets the frontend submit folder-relative paths without requiring desktop-specific APIs.

The active backend architecture treats SQLite as document metadata truth and Milvus as the rebuildable retrieval index. This change should preserve that boundary and avoid introducing a background job system unless one becomes necessary later.

## Goals / Non-Goals

**Goals:**

- Support uploading one file, multiple files, and a selected folder from the knowledge workspace.
- Preserve nested folder-relative paths for uploaded folder contents.
- Save uploaded folder batches under `backend/data/uploads/<batch>/...`.
- Reuse the existing parser, chunker, repository, embedding, and vector index flow for every uploaded file.
- Show a dedicated upload workspace with total progress, current file, per-file status, and per-file errors.
- Allow partial success within a batch.
- Keep path traversal protections around document storage and preview.
- Keep route handlers thin and place path/persistence behavior in `RAGService`.

**Non-Goals:**

- Do not add a durable background job queue in this change.
- Do not add WebSocket or SSE progress streaming for upload parsing.
- Do not change chat streaming behavior.
- Do not replace the existing document parser, chunker, SQLite repository, or Milvus vector store.
- Do not directly edit persisted vector or SQLite files.
- Do not add drag-and-drop unless it naturally falls out of the upload workspace implementation.

## Decisions

### Decision 1: Use A Frontend-Managed Upload Task

The frontend will manage a transient upload task in `frontend/app/knowledge/page.tsx`. The task contains one row per selected file:

```text
UploadFileTask
  id
  file
  relativePath
  size
  status: queued | uploading | parsing | parsed | failed
  progress
  source?
  chunks?
  error?
```

The frontend submits files one at a time or with a small concurrency limit. The first implementation should prefer sequential submission because parsing and embedding are already synchronous and can be resource-intensive.

Rationale:

- Progress is real and easy to understand: completed files over total files.
- One failed file does not poison the whole batch.
- No backend task table, polling API, or queue worker is required.
- It fits the current synchronous upload/parse backend.

Alternatives considered:

- Backend batch endpoint with polling: better for long-running uploads and page refresh resilience, but requires task persistence and lifecycle management.
- SSE/WebSocket progress from backend: richer progress, but adds protocol complexity and still needs task state.
- Browser-only zip upload: easier request shape, but requires server-side archive extraction and adds archive safety concerns.

### Decision 2: Extend The Existing Upload Route With Metadata Fields

The existing `POST /documents/upload` route should continue to accept a single `file` field. It will also accept optional form fields:

```text
relative_path: string | null
batch_id: string | null
```

For a normal single-file upload, `relative_path` can be omitted and the backend uses the uploaded filename. For folder uploads, the frontend sends the browser-provided relative path. `batch_id` groups files selected in the same upload task under one upload root.

Rationale:

- Preserves the current frontend/backend contract for existing callers.
- Avoids duplicating parsing behavior across separate upload endpoints.
- Lets the frontend drive progress per file while the backend remains responsible for storage safety.

Alternative considered:

- Add `POST /documents/upload-batch` that accepts many files in one request. This makes request-level progress less useful once the server begins parsing, and a single request failure can obscure which file failed.

### Decision 3: Backend Owns Relative Path Sanitization

The backend must not trust `relative_path`. `RAGService` will normalize upload paths with these rules:

- Reject empty paths after trimming.
- Reject absolute paths and Windows drive-qualified paths.
- Reject any `..` segment.
- Split on both `/` and `\`.
- Sanitize each path segment while preserving readable Chinese and technical names.
- Validate the final suffix against `SUPPORTED_EXTS`.
- Resolve the final target and verify it remains under `self.upload_dir`.
- If a target already exists, add a timestamp or short suffix before writing.

The stored source should remain relative to `RAG_DATA_DIR`, for example:

```text
uploads/20260616_005900/产品资料包/一级/二级/安装手册.pdf
```

Rationale:

- Frontend path metadata is user-controlled.
- Source paths are later used by document preview and file-serving endpoints.
- Keeping paths readable improves knowledge-list browsing and answer citation traceability.

### Decision 4: Return Per-File Parse/Index Metadata

The upload response should include enough information for the upload workspace row:

```text
doc_id
source
filename
size
parse_status
chunks
error?
```

For successful files, `parse_status` is `parsed` and `chunks` is the total indexed or stored chunk count available from the parse result. For validation errors, the route returns `400` with a concise detail. For unexpected parse/index failures, the route returns an error that the frontend records on that file while continuing the task.

Rationale:

- The frontend does not need to infer completion by refetching the whole document list after each file.
- Existing `DocumentUploadResponse` can be extended compatibly with default fields.

### Decision 5: Upload Workspace Is Part Of The Knowledge Page

The UI should be an upload workspace embedded in the knowledge page rather than a separate route. It should include:

- Buttons for selecting files and selecting a folder.
- A total progress bar.
- Summary counts for queued, active, parsed, and failed files.
- A table/list with relative path, size, status, chunk count, and error.
- A final refresh of the knowledge list after the task completes.

Rationale:

- Keeps document browsing and importing in one workflow.
- Avoids new navigation state.
- Matches the current frontend architecture where `knowledge/page.tsx` owns request flow and `globals.css` owns styling.

## Risks / Trade-offs

- Large folders can take a long time because parsing and embedding are synchronous -> submit sequentially at first, show clear progress, and leave backend task queues for a future change.
- Browser folder upload support depends on `webkitdirectory` -> provide file/multiple-file upload as a fallback.
- Users may close the page mid-task -> completed files remain indexed; queued files are not uploaded. This is acceptable for the first version.
- Duplicate file names or repeated folder uploads may create suffixed files -> surface the returned `source` in the task result and document list.
- Folder uploads can include unsupported files -> mark unsupported files failed or skip them before upload, while keeping the task running.
- Relative path sanitization may change displayed names -> preserve readability where safe and return the actual stored source.

## Migration Plan

1. Extend backend schemas and upload service behavior in a backwards-compatible way.
2. Add tests for safe relative path handling, nested folder persistence, duplicate path handling, unsupported extensions, and route response shape.
3. Add frontend upload workspace state and controls for files and folders.
4. Add progress and per-file status UI.
5. Update docs to describe folder upload behavior and validation.
6. Validate backend route tests and frontend build.

Rollback strategy:

- Keep accepting the existing single-file `POST /documents/upload` shape.
- If the workspace causes issues, hide the folder/upload-task UI while leaving the backend-compatible single-file upload path intact.

## Open Questions

- Should unsupported files be shown as `failed` rows, or silently filtered before the task starts? The recommended first version is to show them as failed rows so users understand what happened.
- Should uploads run strictly sequentially or with a small concurrency limit such as two files? The recommended first version is sequential to avoid competing parse and embedding calls.
