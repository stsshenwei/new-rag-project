## 1. Configuration And Test Fakes

- [x] 1.1 Add disabled-safe environment defaults for Milvus BM25/sparse retrieval, dense/BM25 fan-out, reranker, OCR, and retrieval timeouts.
- [x] 1.2 Add fake hybrid Milvus store, fake reranker, and fake Docling/OCR behavior for service tests.
- [x] 1.3 Add startup tests proving the backend starts when Milvus BM25, reranker, and OCR are disabled.

## 2. Milvus Hybrid Store Boundary

- [x] 2.1 Decide whether to keep `MilvusVectorStore` name or rename it to `MilvusHybridStore`.
- [x] 2.2 Extend the Milvus store interface with dense search, BM25/sparse search, reset, upsert chunks, and document replacement responsibilities.
- [x] 2.3 Add tests for dense-only mode, BM25-disabled mode, and hybrid candidate return shape.
- [x] 2.4 Wire new Milvus BM25 configuration through `build_rag_service()` without changing FastAPI route contracts.

## 3. Milvus Dense + BM25/Sparse Indexing

- [x] 3.1 Verify and document minimum Milvus and pymilvus versions required for built-in BM25/sparse retrieval.
- [x] 3.2 Extend Milvus collection schema creation with dense embedding fields and BM25/sparse-search text fields.
- [x] 3.3 Add collection-version handling or clear reindex behavior for schema changes.
- [x] 3.4 Index child, table, and OCR chunks into Milvus dense and BM25/sparse fields during full ingest and uploaded document indexing.
- [x] 3.5 Replace or delete Milvus records for a document when that document is re-indexed.
- [x] 3.6 Replace SQLite keyword scanning with Milvus BM25/sparse search when enabled, retaining fallback keyword behavior when disabled.

## 4. Hybrid Candidate Merge And Reranking

- [x] 4.1 Refactor retrieval into explicit dense recall, BM25 recall, candidate merge, optional rerank, and parent recall steps.
- [x] 4.2 Preserve vector score, BM25 score, hybrid score, and reranker score metadata on retrieval candidates.
- [x] 4.3 Deduplicate candidates by chunk id while retaining score metadata from each recall source.
- [x] 4.4 Implement local-first reranker provider with disabled/no-op fallback.
- [x] 4.5 Add reranker timeout/error fallback to hybrid ordering.
- [x] 4.6 Add tests for dense-only, BM25-only, shared candidate, reranker reorder, reranker disabled, and reranker failure cases.

## 5. Docling Deep Parsing

- [x] 5.1 Extend Docling parsing to preserve page ranges, captions, figure references, layout coordinates, and parse-source metadata when available.
- [x] 5.2 Ensure fallback parsing returns the same `ParsedDocument` and `ParsedElement` contract.
- [x] 5.3 Add parser tests for rich PDF/DOCX metadata and fallback behavior.
- [x] 5.4 Keep parse preview compatible with existing frontend expectations.

## 6. Structured Table Enhancement

- [x] 6.1 Extend table element metadata to include headers, rows or cell records, caption, row count, column count, and nearby text.
- [x] 6.2 Update table chunk construction to produce deterministic summaries from caption, fields, nearby text, and sampled rows.
- [x] 6.3 Ensure table dense/BM25 retrieval text includes title path, caption, nearby text, summary, fields, and table content.
- [x] 6.4 Ensure table LLM context prefers original Markdown/HTML plus caption and nearby explanation.
- [x] 6.5 Add tests for table metadata persistence, retrieval text generation, and LLM context assembly.

## 7. Optional Docling-First OCR

- [x] 7.1 Add OCR configuration with `OCR_ENABLED=false` default and `OCR_PROVIDER=docling`.
- [x] 7.2 Implement OCR/image-text extraction as an optional Docling parser enhancement when available.
- [x] 7.3 Store OCR text with source, page, confidence, provider, and image/figure metadata when available.
- [x] 7.4 Create indexable OCR chunks when extracted text is non-empty and meets confidence thresholds.
- [x] 7.5 Ensure OCR disabled mode does not require OCR-specific model or binary dependencies.
- [x] 7.6 Add tests for OCR disabled, OCR success, low-confidence filtering, and OCR failure fallback.

## 8. Persistence And Traceability

- [x] 8.1 Confirm SQLite metadata JSON can store new table, layout, OCR, and score metadata without losing existing rows.
- [x] 8.2 Add repository tests for enriched chunk metadata round-tripping.
- [x] 8.3 Ensure final source extraction can trace parent, table, and OCR context back to source, title path, page range, and chunk ids.

## 9. Documentation And Validation

- [x] 9.1 Update `docs/design-docs/backend-rag-pipeline.md` with the enhanced hybrid retrieval pipeline.
- [x] 9.2 Update `docs/ARCHITECTURE.md` and `docs/DEVELOPMENT.md` with Milvus BM25 KeywordSearch, hybrid retriever, local reranker, OCR, and reindex setup notes.
- [x] 9.3 Update `.env.example` with all new configuration keys and disabled-safe defaults.
- [x] 9.4 Run backend unit tests.
- [ ] 9.5 Manually validate ingest and chat retrieval with Milvus BM25/reranker/OCR disabled.
- [ ] 9.6 Manually validate ingest and query retrieval with Milvus BM25 KeywordSearch enabled.

## 10. Requirement Alignment For KeywordSearch

- [x] 10.1 Align `KeywordSearch` implementation docs and code boundaries to Milvus built-in BM25/sparse retrieval.
- [x] 10.2 Define shared `RetrievedChunk`, `KeywordSearch`, `HybridRetriever`, `Reranker`, `ContextBuilder`, `BuiltContext`, `LLMProvider`, `Answer`, and `Citation` models/interfaces.
- [x] 10.3 Keep configuration naming clear that keyword search is Milvus BM25-backed.

## 11. KeywordSearch Implementations

- [x] 11.1 Implement `KeywordSearch.index(chunks)` contract with required `chunk_id`, `doc_id`, `parent_id`, text, score metadata, and filters.
- [x] 11.2 Implement `KeywordSearch.search(query, top_k, filters)` contract returning `chunk_id`, `doc_id`, `parent_id`, and `score`.
- [x] 11.3 Implement `KeywordSearch.delete_by_doc_id(doc_id)` for removing keyword records by document.
- [x] 11.4 Implement Milvus BM25/sparse-backed `KeywordSearch` adapter.
- [x] 11.5 Add tests proving parameter names, error codes, version numbers, technical document names, and command-line snippets are keyword-recallable through Milvus BM25.

## 12. HybridRetriever

- [x] 12.1 Implement `HybridRetriever.retrieve(question, top_k, filters)`.
- [x] 12.2 Ensure retrieval embeds the question before dense vector search.
- [x] 12.3 Retrieve vector top 50 and keyword top 50 by default.
- [x] 12.4 Implement RRF fusion with default `k = 60`.
- [x] 12.5 Add weighted score fusion as a configurable alternative.
- [x] 12.6 Deduplicate fused candidates by `chunk_id`.
- [x] 12.7 Return top 30 fused candidates to reranker by default.
- [x] 12.8 Add tests for dense-only, keyword-only, overlapping results, filters, RRF scoring, and weighted fusion.

## 13. Reranker Interface

- [x] 13.1 Implement `Reranker.rerank(question, chunks, top_k)`.
- [x] 13.2 Add disabled/no-op reranker behavior.
- [x] 13.3 Add configurable reranker provider/model settings.
- [x] 13.4 Default rerank input to fused top 30 and output to top 5-8.
- [x] 13.5 Keep provider boundary replaceable for bge-reranker, jina-reranker, Qwen rerank, or other cross-encoders.
- [x] 13.6 Add tests for disabled rerank, configured model selection, score ordering, and failure fallback.

## 14. ContextBuilder Parent-Child Recall

- [x] 14.1 Implement `ContextBuilder.build(question, reranked_chunks)`.
- [x] 14.2 Query parent chunks by `child.parent_id` and use parent content for LLM context.
- [x] 14.3 Deduplicate selected parents while merging child hit references.
- [x] 14.4 Optionally include adjacent child chunks around matched children.
- [x] 14.5 Include file name, title path, page range, parent content, and matched child summaries in built context.
- [x] 14.6 Enforce final context token budget.
- [x] 14.7 Prefer higher rerank-score parents when context exceeds the token budget.
- [x] 14.8 Add tests for duplicate parents, neighbor inclusion, metadata fields, and token budget trimming.

## 15. LLMProvider And Structured Answers

- [x] 15.1 Implement `LLMProvider.generate_answer(question, context)`.
- [x] 15.2 Add prompt rules requiring answers only from context, explicit insufficient-context response, no fabricated sources, and citations using file/page/section data.
- [x] 15.3 Return structured `Answer` with `answer`, `citations`, `used_chunks`, `confidence`, and optional `debug_info`.
- [x] 15.4 Return citations with `doc_id`, `file_name`, `chunk_id`, `parent_id`, `title_path`, `page_start`, `page_end`, and quote or summary.
- [x] 15.5 Add tests for grounded answer prompt construction, insufficient context handling, citation shape, and debug-info toggle.

## 16. RAG APIs

- [x] 16.1 Add `POST /rag/documents/upload` returning `doc_id` and `status`.
- [x] 16.2 Add `POST /rag/documents/{doc_id}/ingest` returning `doc_id`, `parse_status`, `chunk_count`, and `vector_count`.
- [x] 16.3 Add `POST /rag/query` accepting `question`, optional `doc_ids`, `top_k`, and `filters`.
- [x] 16.4 Ensure `/rag/query` returns `answer`, `citations`, `used_chunks`, and optional `debug_info`.
- [x] 16.5 Add `DELETE /rag/documents/{doc_id}`.
- [x] 16.6 Ensure delete removes original file record, chunk table rows, vector index records, and keyword index records.
- [x] 16.7 Add route/schema tests for upload, ingest, query, and delete APIs.

## 17. Retrieval Debug Info

- [x] 17.1 Add configuration flag controlling debug info in query responses.
- [x] 17.2 Populate `dense_results`.
- [x] 17.3 Populate `bm25_results`.
- [x] 17.4 Populate `fused_results`.
- [x] 17.5 Populate `reranked_results`.
- [x] 17.6 Populate `selected_parent_chunks`.
- [x] 17.7 Populate `final_context_token_count`.
- [x] 17.8 Add tests proving debug info is present when enabled and omitted when disabled.

## 18. YAML RAG Configuration

- [x] 18.1 Add YAML config loading with environment-variable substitution.
- [x] 18.2 Support `rag.parser`, `rag.embedding`, `rag.vector_store`, `rag.keyword_search` with `type: milvus`, `rag.reranker`, `rag.retrieval`, `rag.context`, and `rag.llm` sections.
- [x] 18.3 Map YAML retrieval settings to dense top K, keyword top K, fusion top K, rerank top K, context max tokens, and neighbor inclusion.
- [x] 18.4 Keep `.env` compatibility for existing deployments.
- [x] 18.5 Add example YAML config matching the requested structure.
- [x] 18.6 Add config tests for env substitution, defaults, and provider-specific settings.
