# AGENTS.md

## 1. Project Snapshot

- Repository type: existing full-stack RAG application.
- Frontend: Next.js App Router app in `frontend/` with one main page and global CSS.
- Backend: FastAPI app in `backend/` providing ingest, streaming chat, document browsing, and feedback ingestion.
- Knowledge assets live in `backend/data/`; vector index state is persisted on disk.

## 2. Where To Start

- Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system map.
- Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for local setup and validation commands.
- Read [docs/design-docs/backend-rag-pipeline.md](docs/design-docs/backend-rag-pipeline.md) before changing retrieval or ingest logic.
- Read [docs/design-docs/frontend-chat-ui.md](docs/design-docs/frontend-chat-ui.md) before changing UI behavior or request flow.

## 3. Directory Map

- `frontend/app/page.tsx`: primary UI for chat, dataset list, feedback, and document preview.
- `frontend/app/layout.tsx`: root layout metadata and HTML shell.
- `frontend/app/globals.css`: all page styling for the current frontend.
- `backend/app/main.py`: FastAPI app creation, env loading, route registration, and startup ingest trigger.
- `backend/app/schemas.py`: request and response models.
- `backend/app/services/rag_service.py`: orchestration for ingest, retrieval, source formatting, and feedback write-back.
- `backend/app/services/vector_store.py`: Chroma persistence and OpenAI embedding calls.
- `backend/app/services/document_loader.py`: file discovery, parsing, and chunk splitting.
- `backend/data/`: source knowledge files plus `feedback/` markdown generated from user corrections.
- `backend/chroma_db/`: persisted vector data currently present in this workspace.

## 4. Runtime Boundaries

- Frontend talks only to the backend HTTP API via `NEXT_PUBLIC_API_BASE`.
- Backend owns all OpenAI calls, embeddings, retrieval, file parsing, and feedback persistence.
- `RAGService` is the orchestration layer; keep FastAPI handlers thin and push business logic downward.
- `VectorStore` is the only layer that should directly touch Chroma collection operations.
- `document_loader` is the parsing boundary for supported file formats.

## 5. Source-Of-Truth Files

- Backend API behavior: `backend/app/main.py`
- Retrieval and ingest behavior: `backend/app/services/rag_service.py`
- File parsing and chunking rules: `backend/app/services/document_loader.py`
- Embedding and vector persistence behavior: `backend/app/services/vector_store.py`
- Frontend interaction flow: `frontend/app/page.tsx`
- Dependency manifests: `backend/requirements.txt`, `frontend/package.json`

## 6. Safe Change Workflow

1. Confirm whether the change belongs to frontend, backend, or both.
2. Update the smallest owning module first.
3. Keep API contracts in sync with `backend/app/schemas.py` and frontend request handling.
4. If ingest, retrieval, or feedback behavior changes, update the matching design doc in `docs/design-docs/`.
5. Run the relevant validation commands from `docs/DEVELOPMENT.md`.

## 7. Backend Rules

- Preserve startup env loading and service construction in `backend/app/main.py`.
- Keep route handlers lightweight; prefer adding logic inside `RAGService`.
- Do not hardcode secrets or provider URLs; use env variables only.
- Preserve path safety checks around document access and file writes.
- Treat `backend/data/feedback/` as generated knowledge content, not as a scratch directory.
- Avoid manual edits inside persisted vector index files.

## 8. Frontend Rules

- Keep network calls centralized in `frontend/app/page.tsx` unless the UI is being refactored into components.
- Preserve the SSE parsing contract for `/chat/stream`.
- Keep dataset browsing and document preview behavior aligned with backend endpoints.
- Do not introduce a second styling system without a deliberate migration plan; current styling is all in `globals.css`.

## 9. Data and Persistence Rules

- Supported knowledge file extensions are defined in `document_loader.py`; extend parsing there first.
- Ingest currently rebuilds the collection from source files, so treat it as a destructive reindex of vector data.
- The workspace contains real PDFs and persisted Chroma files; avoid unnecessary rewrites because they can be large.
- Generated feedback markdown becomes part of the retrievable corpus immediately after upsert.

## 10. Environment Checklist

- Backend requires `OPENAI_API_KEY`.
- Backend optionally reads `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `VECTOR_STORE_DIR`, `RAG_DATA_DIR`, `TOP_K`, `MIN_RELEVANCE_SCORE`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `SYSTEM_PROMPT`, and `AUTO_INGEST_ON_STARTUP`.
- Frontend requires `NEXT_PUBLIC_API_BASE`.
- Local Python venvs already exist under `backend/.venv` and `backend/.venv2`; do not assume both are active or identical.

## 11. High-Risk Areas

- Any change to `VectorStore.reset_collection()` or ingest flow can wipe and rebuild embeddings.
- Any change to SSE event framing can break token streaming in the browser.
- Any change to document path resolution or file serving can create traversal or content access issues.
- Any change to feedback write-back affects both dataset listing and future retrieval quality.

## 12. Non-Goals By Default

- Do not edit files under `backend/chroma_db/` directly.
- Do not rewrite large source documents in `backend/data/` unless the task is explicitly about corpus content.
- Do not move environment files or rename API routes without updating both tiers together.

## 13. Good First Validation

- Backend health: `uvicorn app.main:app --reload --port 8000` then `GET /health`
- Manual reindex: `POST /ingest`
- Frontend dev server: `npm run dev`
- End-to-end smoke test: ask one question, verify streamed answer, sources, document preview, and feedback submission path.

## 14. When Updating Docs

- Keep this file short and navigational.
- Put detailed design reasoning into `docs/design-docs/`.
- If architecture changes, update `docs/ARCHITECTURE.md` in the same task.
