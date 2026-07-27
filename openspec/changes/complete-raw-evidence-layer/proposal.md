## Why

The backend already has structured document storage, parent-child chunks, Milvus dense retrieval, and optional Milvus BM25, but keyword retrieval still falls back to an in-process SQLite scan when Milvus BM25 is unavailable. Before adding knowledge graph and agent workflows, the Raw Evidence Layer needs durable keyword indexing, explicit retrieval provider boundaries, and stricter citation traceability back to `document_chunk`.

## What Changes

- Add a SQLite FTS5 keyword index for indexable document chunks.
- Keep FTS5 synchronized with document ingest, document upload, parse reindex, feedback indexing, reset, and delete workflows.
- Introduce provider boundaries for raw evidence retrieval, including vector retrieval and keyword retrieval.
- Replace the scan-based keyword fallback in `RAGService` with SQLite FTS5 search while preserving optional Milvus BM25 behavior.
- Preserve existing parent-child/table/OCR chunk behavior and Milvus `rag_chunk_vectors` indexing.
- Extend `/rag/query` responses with future-compatible evidence fields: `used_entities`, `graph_paths`, and `confidence`.
- Ensure citations and `used_chunks` can be resolved to rows in `document_chunk`.
- Preserve existing `/chat/stream`, upload, parse, dataset listing, and feedback behavior.

## Capabilities

### New Capabilities

- `raw-evidence-layer`: Durable raw document evidence storage, SQLite FTS5 keyword retrieval, hybrid raw evidence retrieval, citation traceability, and provider boundaries for vector and keyword indexes.

### Modified Capabilities

- None.

## Impact

- Backend services: `backend/app/services/document_repository.py`, `backend/app/services/rag_service.py`, `backend/app/services/vector_store.py`, and new provider/interface modules as needed.
- Backend API schemas: `backend/app/schemas.py` for future-compatible `/rag/query` response fields.
- Tests: repository, keyword search, hybrid retrieval, route, and citation traceability coverage.
- Docs: `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, and `docs/design-docs/backend-rag-pipeline.md`.
- No frontend behavior changes are required for this change.
- No Neo4j, knowledge graph extraction, GraphRetriever, agent workflow, permissions, or audit features are included.
