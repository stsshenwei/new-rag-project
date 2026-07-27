## 1. Backend Tests

- [x] 1.1 Add service tests for accepting existing single-file uploads without `relative_path` or `batch_id`.
- [x] 1.2 Add service tests for saving nested uploads under a batch directory while preserving safe relative path segments.
- [x] 1.3 Add service tests rejecting path traversal, absolute paths, Windows drive-qualified paths, empty paths, and unsupported extensions.
- [x] 1.4 Add API route tests for `POST /documents/upload` with optional `relative_path` and `batch_id` form fields.
- [x] 1.5 Add API or service tests proving one failed file can be represented independently from other upload task files.

## 2. Backend Implementation

- [x] 2.1 Extend `DocumentUploadResponse` with backwards-compatible `parse_status`, `chunks`, and optional `error` fields.
- [x] 2.2 Extend `POST /documents/upload` to accept optional `relative_path` and `batch_id` form fields while preserving current callers.
- [x] 2.3 Add upload batch id and relative path normalization helpers to `RAGService`.
- [x] 2.4 Update `RAGService.save_uploaded_document()` to store safe nested uploads under `data/uploads/<batch>/<relative_path>`.
- [x] 2.5 Ensure duplicate upload targets are suffixed without overwriting existing source files.
- [x] 2.6 Return per-file parse/index metadata from upload handling, including stored source and chunk count.

## 3. Frontend Upload Workspace

- [x] 3.1 Add upload task and upload file task types for queued, uploading, parsing, parsed, and failed states.
- [x] 3.2 Add separate controls for selecting files and selecting a folder in the knowledge page.
- [x] 3.3 Read browser folder relative paths from `webkitRelativePath` and fall back to `file.name` for normal file uploads.
- [x] 3.4 Implement sequential upload task processing that posts one file at a time with `relative_path` and `batch_id`.
- [x] 3.5 Keep processing remaining files after individual validation, upload, parse, or index failures.
- [x] 3.6 Refresh the knowledge-base document list after every task reaches parsed or failed status.

## 4. Frontend Presentation

- [x] 4.1 Add an upload workspace panel showing total progress, current file, and task summary counts.
- [x] 4.2 Add a per-file task list showing relative path, size, status, chunk count, and error message.
- [x] 4.3 Add styling in `globals.css` consistent with the existing knowledge-page visual system.
- [x] 4.4 Ensure long nested paths wrap or truncate cleanly on desktop and mobile widths.

## 5. Documentation And Validation

- [x] 5.1 Update backend RAG pipeline docs to describe nested upload persistence and path validation.
- [x] 5.2 Update frontend UI docs to describe the upload workspace and progress behavior.
- [x] 5.3 Run focused backend tests for upload service and API behavior.
- [x] 5.4 Run frontend build or type validation for the knowledge page changes.
- [ ] 5.5 Manually smoke test a single-file upload, multi-file upload, nested folder upload, failed unsupported file, document preview, and knowledge-list refresh.

## 6. Knowledge Document Deletion

- [x] 6.1 Add a delete action to each knowledge table row.
- [x] 6.2 Confirm with the user before deleting a document.
- [x] 6.3 Call `DELETE /rag/documents/{doc_id}` and show per-document deleting state.
- [x] 6.4 Refresh the knowledge-base document list after successful deletion.
- [x] 6.5 Display a delete error and keep the row visible when deletion fails.
- [x] 6.6 Run focused route verification and frontend build after deletion UI changes.
