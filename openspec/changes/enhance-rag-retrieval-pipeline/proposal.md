## Why

The current RAG pipeline already uses Docling-style structured parsing, SQLite metadata, and Milvus vector retrieval, but answer quality is still limited by shallow document structure, weak keyword recall, no final reranking, and incomplete handling of tables and image text. This change upgrades retrieval quality while keeping deployment manageable by using Milvus for both dense vector and BM25/sparse retrieval instead of adding another search service.

## What Changes

- Deepen Docling parsing so PDFs, DOCX files, and other supported rich documents preserve sections, tables, page anchors, captions, figure/image references, layout metadata, and parse provenance where available.
- Add a `KeywordSearch` abstraction backed by Milvus built-in BM25/sparse retrieval.
- Replace the current SQLite keyword scan with Milvus BM25 through `KeywordSearch` while ensuring technical terms, parameter names, error codes, versions, and command-line content are keyword-recallable.
- Add a `HybridRetriever` abstraction that embeds the question, retrieves dense top 50 and keyword top 50, fuses results with RRF or weighted score fusion, deduplicates by chunk id, and returns top 30 candidates for reranking.
- Add a reranker stage after dense/BM25 candidate merge; reranker is configurable, default-disabled, and local-model-first.
- Add a `ContextBuilder` abstraction that expands child hits back to parent context, merges references for duplicate parents, optionally includes neighboring chunks, and enforces a max context token budget.
- Add an `LLMProvider` abstraction that generates structured answers with citations, used chunks, confidence, and optional debug info while refusing to answer beyond retrieved context.
- Add `/rag/documents/upload`, `/rag/documents/{doc_id}/ingest`, `/rag/query`, and `DELETE /rag/documents/{doc_id}` API contracts.
- Add retrieval debug information for dense, keyword, fused, reranked, selected parent chunks, and final context token count behind a configuration flag.
- Add YAML-based RAG configuration for parser, embedding, Milvus vector/BM25 store, reranker, retrieval, context, and LLM settings.
- Enhance table chunks with structured fields/cells, captions, nearby text, deterministic summaries, table-specific retrieval text, and LLM-ready Markdown/HTML context.
- Add optional OCR extraction for image-heavy or scanned documents; OCR is default-disabled and should first use Docling's available OCR/image-text capabilities before introducing heavier OCR dependencies.
- Preserve existing FastAPI route contracts and `/chat/stream` SSE framing.

## Capabilities

### New Capabilities

- `advanced-rag-retrieval`: Defines enhanced ingest and retrieval behavior for Docling deep parsing, Milvus dense recall, Milvus BM25 recall, hybrid retrieval, reranking, context building, structured answer generation, RAG APIs, debug information, structured table enrichment, optional OCR, and source traceability.

### Modified Capabilities

- None.

## Impact

- Backend ingest/retrieval orchestration in `backend/app/services/rag_service.py`.
- Vector store indexing/query behavior in `backend/app/services/vector_store.py`.
- New keyword-search boundary backed by Milvus BM25/sparse retrieval.
- New hybrid retriever, context builder, and LLM provider service boundaries.
- New RAG API routes and schemas.
- Parser/model/chunker boundaries in `backend/app/services/document_parser.py`, `backend/app/models/document_models.py`, and `backend/app/services/document_chunker.py`.
- SQLite metadata persistence in `backend/app/services/document_repository.py`.
- New reranker provider abstraction and local-model configuration.
- Optional OCR integration through Docling-capable parsing first, with future OCR provider extension points.
- Backend environment/YAML configuration examples and docs for Milvus dense/BM25 retrieval, reranker, OCR, LLM provider, debug info, and required reindexing.
