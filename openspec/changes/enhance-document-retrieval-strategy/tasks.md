## 1. Configuration

- [x] 1.1 Add retrieval strategy defaults for RRF weights, rerank thresholds, direct-load chunk limit, and context expansion limits
- [x] 1.2 Load the new strategy values from environment variables and YAML configuration
- [x] 1.3 Update example configuration and retrieval documentation with the new knobs

## 2. Scope Filtering

- [x] 2.1 Extend dense Milvus search expressions to honor `scope.document_ids`
- [x] 2.2 Verify keyword retrieval, hydration, parent recall, and citation extraction reject out-of-scope chunks
- [x] 2.3 Add regression tests for `doc_ids` scoped dense and keyword retrieval

## 3. Weighted Hybrid Fusion

- [x] 3.1 Replace equal RRF fusion with configurable weighted RRF for document retrieval
- [x] 3.2 Preserve single-channel retrieval ordering and original channel score metadata
- [x] 3.3 Add debug metadata for dense rank, keyword rank, weighted contributions, and final hybrid score
- [x] 3.4 Add unit tests for weighted RRF ordering and single-channel behavior

## 4. Rerank Thresholding

- [x] 4.1 Apply `rerank_threshold` to reranked document candidates
- [x] 4.2 Keep the top reranked candidate when no candidate passes threshold but it meets `rerank_fallback_min_score`
- [x] 4.3 Preserve fail-open fallback to hybrid ordering when the reranker fails or times out
- [x] 4.4 Add debug metadata for threshold, fallback threshold, filtered count, and fallback decision
- [x] 4.5 Add tests for threshold pass, top-1 fallback, and reranker failure fallback

## 5. Direct Document Loading

- [x] 5.1 Add repository support to count and load chunks for selected document ids from SQLite
- [x] 5.2 Add direct-load fast path for selected documents at or below `DIRECT_LOAD_MAX_CHUNKS`
- [x] 5.3 Fall back to scoped dense and keyword retrieval when selected documents exceed the direct-load limit
- [x] 5.4 Mark direct-loaded evidence in candidate metadata and retrieval debug output
- [x] 5.5 Add tests for small direct-loaded document sets and large scoped-retrieval fallback

## 6. Context Assembly

- [x] 6.1 Deduplicate final context by chunk id and normalized content signature
- [x] 6.2 Expand short text chunks with previous and next sibling chunks within configured bounds
- [x] 6.3 Merge overlapping or repeated context windows from the same document
- [x] 6.4 Preserve matched child ids, expanded neighbor ids, title path, page range, and source metadata in final citations
- [x] 6.5 Add tests for short-chunk expansion, expansion bounds, deduplication, and citation metadata

## 7. Retrieval Debugging

- [x] 7.1 Extend `/rag/query` debug output with resolved scope, selected document ids, and direct-load decision
- [x] 7.2 Include dense, keyword, fusion, rerank, expansion, and final context stage summaries when retrieval debug is enabled
- [x] 7.3 Ensure debug output remains disabled or compact when retrieval debug is not requested

## 8. Validation

- [x] 8.1 Run backend unit tests for retrieval services
- [x] 8.2 Run an end-to-end scoped document query smoke test against a local knowledge base
- [x] 8.3 Verify FAQ-specific retrieval behavior was not added by this change
