## Why

The current knowledge-base upload flow only handles a single uploaded file at a time and gives limited visibility while the backend stores, parses, chunks, and indexes it synchronously. Users need to import real knowledge packs that are organized as folders with nested files, and they need clear per-file progress and failure feedback instead of a single blocking upload state.

## What Changes

- Add a knowledge upload workspace in the frontend that supports selecting single files, multiple files, and whole folders.
- Preserve folder-relative paths for nested uploads so source paths remain meaningful in the knowledge list, document preview, and citations.
- Extend document upload handling to accept a safe client-provided relative path and optional upload batch identifier.
- Store folder uploads under `backend/data/uploads/<batch>/...` while preventing path traversal, absolute paths, and unsafe file names.
- Parse and index each uploaded file independently by reusing the existing document parsing, chunking, SQLite metadata, and Milvus indexing flow.
- Show total upload progress, current file, per-file status, and per-file errors in the frontend.
- Allow partial success: failed or unsupported files do not stop other files in the same upload task.
- Refresh the knowledge-base document list after upload tasks complete.

## Capabilities

### New Capabilities

- `knowledge-upload-workspace`: Defines file and folder upload behavior, upload task progress, safe nested-path persistence, per-file parse/index status, and knowledge-list refresh behavior.

### Modified Capabilities

- None.

## Impact

- Frontend knowledge workspace in `frontend/app/knowledge/page.tsx`.
- Frontend shared types in `frontend/app/lib/types.ts`.
- Frontend styling in `frontend/app/globals.css`.
- Backend upload route handling in `backend/app/main.py`.
- Backend response schemas in `backend/app/schemas.py`.
- Backend upload orchestration and path safety in `backend/app/services/rag_service.py`.
- Backend tests covering upload path sanitization, folder-relative persistence, partial failures, and API response shape.
- Documentation updates for upload behavior in `docs/design-docs/backend-rag-pipeline.md`, `docs/design-docs/frontend-chat-ui.md`, and development validation notes where appropriate.
