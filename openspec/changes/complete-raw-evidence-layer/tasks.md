## 1. Repository And FTS5 Schema

- [x] 1.1 Add idempotent SQLite FTS5 schema initialization beside `document` and `document_chunk`.
- [x] 1.2 Add repository helpers to insert, replace, delete, and rebuild FTS5 rows from `document_chunk`.
- [x] 1.3 Update `DocumentRepository.replace_chunks()` to synchronize FTS5 rows for child, table, and OCR chunks.
- [x] 1.4 Update `DocumentRepository.reset()` and `delete_document()` to clear matching FTS5 rows.
- [x] 1.5 Add a repository keyword search method that returns ranked chunk hits with chunk metadata and score fields.

## 2. Raw Retrieval Provider Boundaries

- [x] 2.1 Add protocol or interface definitions for vector retrieval, keyword retrieval, and evidence lookup.
- [x] 2.2 Adapt the existing `MilvusVectorStore` to satisfy the vector retrieval and mutation provider boundary without changing its external behavior.
- [x] 2.3 Add a SQLite FTS5 keyword provider backed by `DocumentRepository`.
- [x] 2.4 Normalize SQLite FTS5, Milvus BM25, and dense hits into a common retrieval hit shape.

## 3. RAG Service Integration

- [x] 3.1 Wire the SQLite FTS5 keyword provider into `RAGService`.
- [x] 3.2 Replace the Python scan-based keyword fallback with FTS5 keyword retrieval.
- [x] 3.3 Preserve Milvus BM25 keyword retrieval when `MILVUS_BM25_ENABLED=true`.
- [x] 3.4 Preserve existing RRF fusion, matched query traces, reranking behavior, and parent recall behavior.
- [x] 3.5 Ensure feedback-created documents are indexed into SQLite FTS5 as part of the existing parse-and-index path.

## 4. Query Response And Citation Traceability

- [x] 4.1 Extend `RagQueryResponse` with `used_entities`, `graph_paths`, and `confidence`.
- [x] 4.2 Update `RAGService.answer_query()` to populate future-compatible defaults for raw evidence responses.
- [x] 4.3 Add citation and used chunk validation so returned chunk ids resolve to `document_chunk`.
- [x] 4.4 Add a retrieval confidence calculation based on selected evidence scores and evidence availability.
- [x] 4.5 Ensure insufficient-evidence answers continue to clearly state that the answer cannot be determined from available evidence.

## 5. Tests

- [x] 5.1 Add repository tests for FTS5 schema creation, insert, replace, reset, delete, and rebuild behavior.
- [x] 5.2 Add keyword retrieval tests for exact model names, API names, configuration keys, and error-code-like terms.
- [x] 5.3 Add RAG service tests proving SQLite FTS5 replaces the scan fallback when Milvus BM25 is disabled.
- [x] 5.4 Add hybrid retrieval tests proving dense and keyword hits still fuse by chunk identity.
- [x] 5.5 Add API route tests for `/rag/query` response fields, confidence, citation traceability, and empty graph/entity fields.
- [x] 5.6 Add delete consistency tests proving document deletion removes SQLite chunk rows, FTS5 rows, and Milvus document vectors.

## 6. Documentation And Validation

- [x] 6.1 Update `docs/design-docs/backend-rag-pipeline.md` with SQLite FTS5 and provider boundaries.
- [x] 6.2 Update `docs/ARCHITECTURE.md` with the completed Raw Evidence Layer topology.
- [x] 6.3 Update `docs/DEVELOPMENT.md` with validation commands and FTS5 notes.
- [x] 6.4 Run the relevant backend unit/API tests.
- [x] 6.5 Run a manual smoke test for upload or parse, keyword query, semantic query, `/rag/query`, citation preview, and delete consistency.
