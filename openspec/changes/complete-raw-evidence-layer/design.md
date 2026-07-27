## Context

The backend already has a structured RAG pipeline: uploaded and local files are parsed into `ParsedDocument`, split into parent-child/table/OCR `Chunk` records, stored in SQLite through `DocumentRepository`, indexed into Milvus through `MilvusVectorStore`, and retrieved through `RAGService`. Query understanding, RRF fusion, parent recall, optional reranking, streaming chat, feedback write-back, and long-term memory already exist.

The weak point is the raw keyword evidence path. When Milvus BM25 is disabled or unavailable, keyword retrieval currently falls back to scanning SQLite chunk content in Python. That fallback is useful for development, but it is not a durable enterprise evidence index. The Raw Evidence Layer should make raw source chunks, vector retrieval, keyword retrieval, and citation traceability explicit before graph and agent layers are added.

This change is intentionally limited to raw evidence. Knowledge graph extraction, GraphRetriever, agent routing, and governance will build on this layer in later changes.

## Goals / Non-Goals

**Goals:**

- Add SQLite FTS5 keyword indexing for indexable document chunks.
- Keep FTS5 rows synchronized with `document_chunk` mutations.
- Preserve Milvus `rag_chunk_vectors` dense retrieval and optional Milvus BM25.
- Introduce explicit retrieval provider boundaries so vector and keyword implementations can be replaced later.
- Make `/rag/query` response shape future-compatible with KG and Agent fields while keeping existing callers working.
- Ensure citations and `used_chunks` resolve back to `document_chunk`.
- Preserve existing upload, parse, ingest, chat streaming, feedback, and document browsing behavior.

**Non-Goals:**

- Neo4j or any graph database integration.
- Entity extraction, entity resolution, or `entity_mention` storage.
- GraphRetriever or graph path retrieval.
- QueryRouter, RetrievalPlanner, or finite-state Agent workflow.
- Tenant permission filtering, audit workflow, graph review, or evaluation datasets.
- Frontend UI redesign.

## Decisions

### Decision 1: Use SQLite FTS5 as the default keyword fallback

Add an FTS5 virtual table beside `document_chunk` and index only chunks useful for retrieval: `child`, `table`, and `ocr`. Parent chunks remain the context recall target, but child/table/OCR chunks are the search units.

Rationale: SQLite already owns durable chunk metadata. FTS5 gives exact-term and BM25-style ranking without requiring OpenSearch or Milvus BM25 during local development.

Alternative considered: keep the current Python scan fallback. This was rejected because it does not scale, does not provide real ranking, and hides keyword retrieval behind `RAGService` implementation details.

### Decision 2: Synchronize FTS5 inside the repository boundary

`DocumentRepository.replace_chunks()`, `reset()`, and `delete_document()` should update both `document_chunk` and the FTS5 table in the same SQLite transaction. This keeps raw evidence state consistent without requiring callers to remember a second indexing step.

Rationale: `document_chunk` is the source of truth. The keyword index is derived from it and should not drift.

Alternative considered: add a separate indexing service called by `RAGService`. That would make provider replacement easier, but it also increases the chance of partial updates during upload, parse, feedback, and delete flows.

### Decision 3: Introduce provider boundaries without a large refactor

Add small interfaces or protocols around:

- vector retrieval and vector mutation, backed initially by `MilvusVectorStore`
- keyword retrieval, backed by SQLite FTS5 and optionally bypassed by Milvus BM25 when enabled
- evidence lookup, backed by `DocumentRepository`

Rationale: later KG and Agent changes need callable tools. The first step is to give raw retrieval a stable interface while keeping `RAGService` as the existing orchestration layer.

Alternative considered: fully split `RAGService` into separate ingest, retrieval, and answering services in this change. That was rejected because this change should preserve behavior and keep the blast radius small.

### Decision 4: Preserve optional Milvus BM25 precedence

When `MILVUS_BM25_ENABLED=true`, keyword retrieval can continue to use Milvus sparse search. When it is disabled or unavailable, SQLite FTS5 is the default keyword provider.

Rationale: Milvus BM25 is useful in production-like deployments, while SQLite FTS5 is a dependable local and fallback path. Both should return the same hit shape for fusion.

Alternative considered: replace Milvus BM25 entirely with FTS5. That would simplify code but remove a capability already documented and tested.

### Decision 5: Make citation traceability explicit

Every citation returned by `/rag/query` must contain identifiers that can resolve to `document_chunk`, including `doc_id`, `chunk_id`, and `parent_id` where available. `used_chunks` must contain existing child/table/OCR chunk IDs.

Rationale: graph and agent layers will later rely on raw chunk IDs as evidence anchors. If raw citations are loose labels, later citation verification cannot be trusted.

Alternative considered: keep citation labels as display-only source strings. That was rejected because display labels are not enough for verification, auditing, or graph relation source binding.

### Decision 6: Add future-compatible response fields now

Extend `RagQueryResponse` with `used_entities`, `graph_paths`, and `confidence`. For this change, graph and entity fields are empty lists. `confidence` is derived from retrieval evidence strength and evidence availability.

Rationale: future GraphRetriever and Agent workflows can fill these fields without another response-shape migration. Existing clients that ignore unknown fields continue to work.

Alternative considered: wait until KG/Agent changes. That delays contract stabilization and makes later frontend/API compatibility harder.

## Risks / Trade-offs

- FTS5 may not be enabled in every SQLite build -> Detect initialization failures clearly and keep tests focused on the project Python environment.
- Two keyword paths can diverge -> Normalize Milvus BM25 and SQLite FTS5 hits into the same hit shape before fusion.
- Repository responsibilities grow -> Keep FTS5 synchronization narrow and derived from `document_chunk`; do not move retrieval orchestration into the repository.
- Existing tests may rely on scan fallback behavior -> Update tests to assert keyword behavior through the provider contract rather than private scan details.
- Confidence can be overinterpreted -> Treat confidence as retrieval confidence, not truth confidence, and document the calculation.

## Migration Plan

1. Add FTS5 schema initialization with idempotent migrations.
2. Backfill FTS5 rows from existing `document_chunk` rows on repository initialization or through a safe sync method.
3. Update repository mutation methods to keep FTS5 synchronized.
4. Add keyword provider and replace scan fallback in `RAGService`.
5. Extend `/rag/query` response fields with compatible defaults.
6. Add tests for FTS5, retrieval fusion, citation traceability, and delete consistency.
7. Update architecture and backend RAG pipeline docs.

Rollback is straightforward: disable use of the SQLite FTS5 provider and return to dense retrieval or Milvus BM25 while leaving `document_chunk` untouched. The FTS5 table is derived data and can be rebuilt from `document_chunk`.

## Open Questions

- Should FTS5 include parent chunks for direct keyword search, or only child/table/OCR chunks with parent recall? The recommended default is child/table/OCR only.
- Should the FTS5 tokenizer use the default tokenizer first, or introduce tokenizer configuration for Chinese/domain text in a later tuning change? The recommended default is default FTS5 tokenization plus existing query understanding.
- Should confidence be exposed as a simple max/average retrieval score now, or a small structured object later? The recommended default is a single numeric field now and richer debug details under `debug_info`.
