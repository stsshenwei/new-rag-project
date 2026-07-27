## 1. Baseline And Scope

- [x] 1.1 Review current knowledge page, upload workspace remnants, multi-KB APIs, and documents API behavior; record exact focused validation commands.
- [x] 1.2 Confirm no implementation step uploads existing local documents or sends their contents to external providers without explicit user approval.
- [x] 1.3 Add or update frontend type definitions for creation wizard settings, upload batch, upload file task, document filters, view mode, and effective provider status.

## 2. Backend Upload Batch Model

- [x] 2.1 Add final SQLite schema support for scoped upload batches and upload file tasks with workspace/KB foreign keys, timestamps, status, settings JSON, and sanitized errors.
- [x] 2.2 Add repository tests for creating batches, adding files, updating statuses, fetching by KB scope, rejecting cross-KB access, and terminal states.
- [x] 2.3 Implement repository/service methods for batch lifecycle transitions: draft, uploading, ready_to_process, processing, completed, partial_failed, failed, and canceled.
- [x] 2.4 Implement repository/service methods for file task lifecycle transitions: pending, uploaded, parsing, indexed, enrichment_pending, completed, failed, and canceled.
- [x] 2.5 Ensure clean-rebuild resets upload batch/task state consistently with managed source deletion.

## 3. Staged Upload API

- [x] 3.1 Add request/response schemas for upload batch create, settings update, file upload, confirm, status fetch, cancel, and file retry.
- [x] 3.2 Add scoped FastAPI routes under `/knowledge-bases/{knowledge_base_id}/upload-batches`.
- [x] 3.3 Reuse existing path sanitization and managed upload storage while saving file tasks without immediate parse/index work.
- [x] 3.4 Implement batch confirmation so processing starts only after explicit confirmation and persists visible state before each phase.
- [x] 3.5 Implement targeted retry for failed file tasks without duplicating active documents.
- [x] 3.6 Preserve or document compatibility for the existing `/documents/upload` path while keeping the new knowledge UI on staged endpoints.
- [x] 3.7 Add API tests for active KB success, archived KB rejection, cross-KB rejection, pending-without-provider-calls, partial failure, retry, cancel, and reset-required behavior.

## 4. Processing Orchestration

- [x] 4.1 Refactor upload processing to call existing parser, chunker, document repository, vector store, and enrichment services from a batch/file task context.
- [x] 4.2 Persist document ID, chunk count, status, and sanitized error on each file task after every major processing phase.
- [x] 4.3 Ensure processing carries `KnowledgeBaseScope` through parse, chunk, vector upsert, FTS, KG, enrichment, preview, and deletion boundaries.
- [x] 4.4 Add tests proving one file failure does not block completed files from appearing in the selected KB.
- [x] 4.5 Add tests proving selected-but-unconfirmed files are not parsed, indexed, embedded, or enriched.

## 5. Knowledge Creation Wizard UI

- [x] 5.1 Split the knowledge page into focused components without changing routes or adding a second styling system.
- [x] 5.2 Replace the simple create dialog with a WeKnora-like creation wizard with a left configuration rail and basic information section.
- [x] 5.3 Add Document type selection and disabled placeholders for unsupported FAQ/Wiki/future types.
- [x] 5.4 Add model configuration, vector storage, parser engine, chunk settings, image/OCR, audio, graph, and advanced sections with unsupported options disabled or read-only.
- [x] 5.5 Submit supported requested settings, display effective provider configuration after creation, and preserve input on validation failure.
- [x] 5.6 Add frontend validation coverage for empty name, duplicate/backend error, disabled unsupported type, and successful navigation to the created KB.

## 6. Document Workspace UI

- [x] 6.1 Add a Weknora-like document toolbar with search, tag, type, status, source, time range, refresh, upload menu, and grid/list mode controls.
- [x] 6.2 Add backend-supported document query parameters or a scoped document search endpoint for KB-safe filtering.
- [x] 6.3 Implement document grid cards with title, preview/summary, file type, status, updated time, and action menu.
- [x] 6.4 Implement compact list mode with stable columns for name, status, chunks, type, source, updated time, and actions.
- [x] 6.5 Add bulk selection and scoped bulk action plumbing, with partial failure display.
- [x] 6.6 Ensure preview, delete, retry, and future actions always include active KB scope and reject cross-KB leakage.
- [x] 6.7 Add responsive CSS for desktop and mobile with no text overlap, horizontal overflow, or card nesting.

## 7. Staged Upload UI

- [x] 7.1 Replace direct file-input processing with an upload action menu for upload documents, upload folder, import webpage, and online editing.
- [x] 7.2 Route document/folder upload choices into a pending upload dialog before any processing begins.
- [x] 7.3 Show pending file count, scrollable file list, relative paths, file sizes, remove actions, and cancel behavior.
- [x] 7.4 Add the upload confirmation configuration panel for parser engine, chunking, retrieval switches, question generation, graph, OCR/multimodal/audio availability, and effective settings.
- [x] 7.5 Implement staged file transfer to the batch API and show batch/file progress from backend task state.
- [x] 7.6 Add task monitor UI for completed, partial_failed, failed, canceled, retrying, and reset-required states.
- [x] 7.7 Keep webpage import and online editing entries disabled or unavailable until their backend capabilities exist.

## 8. Documentation And Validation

- [x] 8.1 Update `docs/design-docs/frontend-chat-ui.md` with the WeKnora-like knowledge management contract and staged upload UI behavior.
- [x] 8.2 Update `docs/design-docs/backend-rag-pipeline.md` with upload batch/task lifecycle, provider-safety boundary, and KB scope requirements.
- [x] 8.3 Update README/API notes for staged upload endpoints and the fact that selecting files does not process them until confirmation.
- [x] 8.4 Run focused backend tests for upload batch repository, API, processing, KB isolation, reset-required, and legacy upload compatibility.
- [x] 8.5 Run frontend type/build validation and any existing frontend tests.
- [ ] 8.6 Manually smoke test creation wizard, disabled unsupported options, pending upload cancel, confirm processing using safe test fixtures, partial failure, retry, document filters, grid/list modes, mobile layout, and chat preselection.
- [x] 8.7 Run `openspec validate make-knowledge-management-weknora-like --strict` and fix proposal/design/spec/task mismatches.
