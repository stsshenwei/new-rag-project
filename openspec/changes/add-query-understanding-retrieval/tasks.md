## 1. Query Understanding Tests

- [x] 1.1 Add tests for query-understanding result models, defaults, and serialization.
- [x] 1.2 Add terminology dictionary loader tests for canonical terms, aliases, and missing files.
- [x] 1.3 Add a normalization test where `8个电口` produces `RJ-45` terms and retrieval query variants.
- [x] 1.4 Add fallback tests for disabled query understanding and invalid terminology dictionaries.
- [x] 1.5 Add tests for retrieval query deduplication and maximum query count enforcement.
- [x] 1.6 Add optional LLM rewrite tests with a fake rewrite client, including invalid output fallback.
- [x] 1.7 Add RAG service retrieval tests proving expanded queries are used and duplicate chunks are fused.

## 2. Query Understanding Implementation

- [x] 2.1 Add a query-understanding service module and response models.
- [x] 2.2 Add a terminology dictionary loader with a safe empty-dictionary default.
- [x] 2.3 Implement dictionary-first normalization with applied-term metadata.
- [x] 2.4 Generate bounded retrieval query variants from the original query, normalized query, and aliases.
- [x] 2.5 Add an optional LLM rewrite provider with structured output validation and fail-open fallback.
- [x] 2.6 Add configuration for enablement, rewrite enablement, terminology path, and max query count.

## 3. Retrieval Integration

- [x] 3.1 Wire query understanding into `RAGService.hybrid_retrieve_hits()`.
- [x] 3.2 Run existing dense and keyword retrieval for bounded query variants.
- [x] 3.3 Fuse and deduplicate multi-query hits by chunk identity while preserving trace metadata.
- [x] 3.4 Preserve raw-query retrieval behavior when query understanding is disabled or fails.
- [x] 3.5 Include query-understanding metadata in retrieval debug output only when debug output is enabled.
- [x] 3.6 Preserve `/chat/stream` SSE framing and `/rag/query` response compatibility.

## 4. Configuration And Documentation

- [x] 4.1 Add an example terminology dictionary covering `电口`/`RJ-45` and `光口`/`SFP`.
- [x] 4.2 Update environment or RAG configuration examples with query-understanding settings.
- [x] 4.3 Update backend RAG pipeline documentation with the new query-understanding flow and fallback behavior.
- [x] 4.4 Update development documentation with validation commands and a sample `8个电口` smoke test.

## 5. Validation

- [x] 5.1 Run focused query-understanding unit tests.
- [x] 5.2 Run retrieval and RAG service tests covering expanded multi-query retrieval.
- [x] 5.3 Run the backend regression test set relevant to ingest, retrieval, and chat.
- [x] 5.4 Manually smoke test a query like `8个电口` against content containing `RJ-45` and verify retrieval debug output.
