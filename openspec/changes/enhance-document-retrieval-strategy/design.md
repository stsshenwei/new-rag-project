## Context

The project already has a document-oriented RAG pipeline with Milvus dense retrieval, optional Milvus BM25, SQLite FTS5 fallback, query understanding, RRF fusion, optional reranking, parent recall, and traceable citations.

The gaps surfaced by comparing `召回策略.docx` and Weknora source are not about adding another retrieval type first; they are about making the document retrieval path stricter and more controllable:

- `doc_ids` constraints are accepted by `/rag/query`, but dense Milvus retrieval currently scopes only workspace and knowledge base.
- RRF fusion uses equal rank contribution instead of configurable vector/keyword weights.
- Rerank is optional but only sorts/top-k filters; it does not apply threshold, fallback, or transparent debug reporting.
- Explicit document selection still goes through ordinary retrieval rather than a direct-load fast path.
- Context assembly recalls parents, but lacks Weknora-style short chunk expansion, overlap merging, and stronger duplicate suppression.

This design targets document knowledge bases only. FAQ knowledge base retrieval, FAQ indexing modes, negative-question filtering, and FAQ answer backfill are excluded.

## Goals / Non-Goals

**Goals:**

- Enforce `workspace_id`, `knowledge_base_id`, and `doc_ids` consistently in dense, keyword, hydration, parent recall, and citation extraction.
- Add configurable weighted RRF with defaults aligned to the Weknora-inspired strategy: `rrf_k=60`, `vector_weight=0.7`, `keyword_weight=0.3`.
- Add rerank threshold filtering with a deterministic top-1 fallback for low-but-usable results.
- Add direct loading for explicitly selected documents when the selected indexed chunk count is below a safety limit.
- Improve final document context quality with neighbor expansion for short chunks, overlap-aware merging, and duplicate removal.
- Extend retrieval debug output so every stage is explainable.
- Preserve fail-open behavior for optional providers and fail-closed behavior for scope constraints.

**Non-Goals:**

- Do not implement FAQ-specific retrieval in this change.
- Do not add multi-vector-store binding or tenant cross-store fan-out.
- Do not replace Milvus or SQLite.
- Do not add new external services.
- Do not change document parsing or chunking fallback strategies.

## Decisions

### Decision 1: Scope filtering is a retrieval invariant

All retrieval channels must treat `KnowledgeBaseScope` as authoritative. Dense Milvus search should include `doc_id in [...]` when `scope.document_ids` is non-empty. Keyword search already applies doc filters through SQLite FTS5 and should retain equivalent behavior for Milvus BM25. Hydration and parent recall should continue to reject candidates outside the requested scope.

Rationale: A user who selects a specific document expects retrieval to stay in that document. Returning full-KB dense hits is both confusing and unsafe for enterprise document workflows.

Alternative considered: Filter dense results after Milvus returns them. This is simpler but can starve recall because top-k may be consumed by out-of-scope chunks before post-filtering.

### Decision 2: Weighted RRF becomes the default document fusion method

Fusion should score candidates as:

```text
score = vector_weight / (rrf_k + vector_rank) + keyword_weight / (rrf_k + keyword_rank)
```

Defaults:

```text
rrf_k = 60
vector_weight = 0.7
keyword_weight = 0.3
```

If only one channel returns candidates, retrieval should keep that channel's original order and score metadata while still producing a stable `hybrid_score`.

Rationale: Dense and keyword scores use different scales. Rank fusion avoids score calibration, while weights let semantic retrieval lead without losing exact term matches.

Alternative considered: Linear normalized score blending. This requires provider-specific normalization and is fragile across Milvus dense, Milvus BM25, and SQLite FTS5.

### Decision 3: Rerank applies threshold filtering with fallback

When rerank is enabled and available, the reranker should:

- score the fused candidate list
- drop candidates below `rerank_threshold`
- if none pass, keep the top reranked candidate when its score is at least `rerank_fallback_min_score`
- otherwise fall back to no-evidence behavior rather than invent context

Defaults:

```text
rerank_threshold = 0.3
rerank_fallback_min_score = 0.15
rerank_top_k = existing configured RERANKER_TOP_N
```

Provider failure or timeout still falls back to hybrid ordering, because provider availability should not break chat.

Rationale: Rerank should improve precision, but a too-strict threshold should not silently erase the only usable evidence.

Alternative considered: Always return reranker top-k. This preserves recall but does not filter weak evidence and makes `reranker_score` less useful as a confidence signal.

### Decision 4: Explicit document selection gets a direct-load fast path

When `/rag/query` receives `doc_ids`, the service should count indexable chunks for those documents. If the total is at or below `DIRECT_LOAD_MAX_CHUNKS` (default 50), retrieval should load those chunks directly from SQLite, mark them as direct-loaded evidence, assign a high initial score, and skip dense/keyword retrieval for those documents. If the total exceeds the limit, retrieval should fall back to scoped dense/keyword retrieval.

Rationale: Direct selection is an intent signal stronger than semantic similarity. It also avoids missing small documents due to embedding or keyword mismatch.

Alternative considered: Always direct-load selected documents. This risks context explosion for large manuals.

### Decision 5: Context assembly stays document-first and source-traceable

The final context stage should operate on document chunks only:

1. deduplicate candidates by chunk id and content signature
2. resolve child/table/OCR hits to authoritative SQLite rows
3. expand short text chunks with previous/next sibling chunks until a minimum length or maximum length is reached
4. merge overlapping or repeated content windows within the same document
5. group child hits by parent where parent content is the better LLM context
6. keep citation metadata for matched child ids, expanded neighbor ids, title path, page range, and source document

Rationale: Parent recall alone can be either too broad or too repetitive. Neighbor expansion helps tiny chunks, while overlap merging keeps context dense.

Alternative considered: Always pass full parents. This is simpler but can waste context and pull unrelated content into the prompt.

### Decision 6: Retrieval configuration remains backend-first

New knobs should be available through env and YAML config first:

- `RRF_K`
- `RRF_VECTOR_WEIGHT`
- `RRF_KEYWORD_WEIGHT`
- `RERANKER_THRESHOLD`
- `RERANKER_FALLBACK_MIN_SCORE`
- `DIRECT_LOAD_MAX_CHUNKS`
- `CONTEXT_SHORT_CHUNK_MIN_CHARS`
- `CONTEXT_EXPANDED_CHUNK_MAX_CHARS`

The frontend can surface these later, but this change should not block on UI configuration.

Rationale: Retrieval quality work needs testable runtime defaults before adding more UI surface area.

### Decision 7: Debug output is part of the retrieval contract

When retrieval debug is enabled, `/rag/query` should expose enough metadata to explain decisions:

- resolved scope and selected doc ids
- direct-load decision and skipped document ids
- dense and keyword candidates with rank, score, and matched query
- weighted RRF contributions
- rerank scores, threshold, filtered count, fallback decision
- expanded neighbor chunk ids
- final selected parent/context token estimate

Rationale: The user is tuning enterprise document retrieval. Debug visibility is not optional polish; it is how false negatives and noisy hits are diagnosed.

## Risks / Trade-offs

- [Risk] Weighted RRF defaults may improve common cases but hurt exact-ID-heavy corpora. -> Mitigation: expose weights through env/YAML and record per-channel contributions in debug output.
- [Risk] Direct loading may overwhelm context for selected large documents. -> Mitigation: enforce a chunk-count cap and fall back to normal scoped retrieval above the cap.
- [Risk] Rerank thresholds vary by provider score scale. -> Mitigation: keep configurable thresholds and fail safely to hybrid order on provider errors.
- [Risk] Neighbor expansion can introduce irrelevant adjacent content. -> Mitigation: apply only to short text chunks, preserve source/neighbor ids, and cap expanded length.
- [Risk] Additional debug metadata can be noisy. -> Mitigation: emit only when retrieval debug is enabled.

## Migration Plan

1. Add configuration defaults while preserving existing behavior when unset.
2. Add scope/doc filtering to dense retrieval and tests before changing ranking behavior.
3. Add weighted RRF behind defaults equivalent to the intended strategy.
4. Add rerank threshold/fallback and debug output.
5. Add direct-load and context expansion with safety caps.
6. Update docs and examples after tests pass.

Rollback is straightforward: disable reranker, set RRF weights to equal values, set direct-load max chunks to `0`, and disable context neighbor expansion via configuration.

## Open Questions

- Should direct-loaded evidence bypass rerank entirely, or should direct-loaded chunks be included in rerank with a source prior?
- Should neighbor expansion use stored sibling order only, or should it also use page/section metadata when available?
- Should retrieval settings eventually live per knowledge base, globally, or both?
