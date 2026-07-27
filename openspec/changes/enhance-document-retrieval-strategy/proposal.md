## Why

The current document retrieval pipeline has dense retrieval, keyword retrieval, RRF fusion, parent recall, and optional reranking, but several enterprise retrieval controls are still incomplete: `doc_ids` constraints do not fully apply to dense Milvus search, RRF is unweighted, reranking lacks threshold/fallback behavior, and context merging is lighter than the Weknora-inspired strategy captured in `召回策略.docx`.

This change improves retrieval quality and predictability for document knowledge bases while explicitly excluding FAQ-specific retrieval so the scope stays focused.

## What Changes

- Apply explicit document constraints consistently across dense and keyword retrieval.
- Add weighted RRF for document hybrid retrieval with configurable vector/keyword weights.
- Add rerank threshold filtering, top-1 fallback, and debug metadata for filtered candidates.
- Add direct loading for explicitly selected documents when the selected chunk count stays within a safety limit.
- Improve context assembly with short-chunk neighbor expansion, stronger duplicate removal, and clearer source traceability.
- Expose retrieval strategy parameters through backend configuration and debug output.
- Keep FAQ knowledge-base retrieval out of scope for this change.

## Capabilities

### New Capabilities
- `document-retrieval-strategy`: Covers document-only retrieval strategy controls, including scoped dense retrieval, weighted RRF, rerank threshold fallback, direct document loading, context expansion, deduplication, and debug traceability.

### Modified Capabilities
None.

## Impact

- Backend retrieval orchestration in `backend/app/services/rag_service.py`.
- Milvus scope/filter expression handling in `backend/app/services/vector_store.py`.
- Optional retrieval model boundaries in `backend/app/services/reranker.py`, `backend/app/services/context_builder.py`, and retrieval debug output.
- API behavior for `/rag/query` when `doc_ids`, `knowledge_base_id`, or `knowledge_base_ids` are provided.
- Configuration defaults in `backend/app/main.py`, `backend/app/services/rag_config.py`, `backend/rag_config.example.yaml`, and `.env.example`.
- Tests covering scoped retrieval, weighted RRF ordering, rerank fallback, direct loading, context expansion, and debug metadata.
