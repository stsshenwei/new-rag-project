## ADDED Requirements

### Requirement: Document scope constraints apply to every retrieval channel
The system SHALL apply requested workspace, knowledge base, and document constraints consistently across document dense retrieval, keyword retrieval, candidate hydration, parent recall, and citation extraction.

#### Scenario: Dense retrieval honors selected documents
- **WHEN** `/rag/query` is called with `doc_ids`
- **THEN** dense Milvus retrieval only returns candidates whose `doc_id` is in the requested document id set

#### Scenario: Keyword retrieval honors selected documents
- **WHEN** `/rag/query` is called with `doc_ids`
- **THEN** keyword retrieval only returns candidates whose `doc_id` is in the requested document id set

#### Scenario: Out-of-scope candidates are discarded
- **WHEN** a retrieval provider returns a candidate outside the requested workspace, knowledge base, or document set
- **THEN** candidate hydration and parent recall discard that candidate before answer generation

### Requirement: Document hybrid retrieval uses weighted RRF
The system SHALL fuse document dense and keyword candidates with configurable weighted reciprocal rank fusion.

#### Scenario: Dense and keyword candidates receive weighted RRF contributions
- **WHEN** both dense and keyword retrieval return candidates
- **THEN** each fused candidate receives `hybrid_score = vector_weight / (rrf_k + vector_rank) + keyword_weight / (rrf_k + keyword_rank)` using default `rrf_k = 60`, `vector_weight = 0.7`, and `keyword_weight = 0.3`

#### Scenario: Single-channel retrieval remains usable
- **WHEN** only dense retrieval or only keyword retrieval returns candidates
- **THEN** the system keeps those candidates in provider rank order and preserves their original channel score metadata

#### Scenario: Weighted RRF metadata is debuggable
- **WHEN** retrieval debug output is enabled
- **THEN** debug output includes each fused candidate's dense rank, keyword rank, vector contribution, keyword contribution, and final hybrid score when available

### Requirement: Rerank threshold filtering has a safe fallback
The system SHALL apply configurable rerank threshold filtering when reranking document candidates and SHALL preserve safe fallback behavior.

#### Scenario: Rerank removes weak candidates
- **WHEN** reranking is enabled and candidate rerank scores are returned
- **THEN** candidates below `rerank_threshold` are excluded from final context selection

#### Scenario: Rerank keeps top candidate fallback
- **WHEN** reranking is enabled and no candidate meets `rerank_threshold`
- **THEN** the highest-scoring reranked candidate is kept if its score is at least `rerank_fallback_min_score`

#### Scenario: Rerank failure falls back to hybrid order
- **WHEN** reranking is enabled but the reranker fails or times out
- **THEN** the request completes using pre-rerank hybrid ordering and records the rerank failure in debug output when debug is enabled

#### Scenario: Rerank debug explains filtering
- **WHEN** retrieval debug output is enabled
- **THEN** debug output includes rerank threshold, fallback threshold, input candidate count, filtered candidate count, and whether fallback was used

### Requirement: Explicit document selection can direct-load small document sets
The system SHALL direct-load explicitly selected document chunks when the selected document set is safely small.

#### Scenario: Small selected document set is direct-loaded
- **WHEN** `/rag/query` includes `doc_ids` and the total indexable chunk count for those documents is at or below `DIRECT_LOAD_MAX_CHUNKS`
- **THEN** the system loads those chunks from SQLite, marks them as direct-loaded evidence, and does not require dense or keyword similarity to include them as candidates

#### Scenario: Large selected document set falls back to scoped retrieval
- **WHEN** `/rag/query` includes `doc_ids` and the total indexable chunk count is above `DIRECT_LOAD_MAX_CHUNKS`
- **THEN** the system skips direct loading and uses normal dense and keyword retrieval scoped to those document ids

#### Scenario: Direct-load decision is visible
- **WHEN** retrieval debug output is enabled
- **THEN** debug output includes whether direct loading was used, the selected document ids, loaded chunk count, skipped document ids, and configured chunk limit

### Requirement: Document context assembly expands and deduplicates evidence
The system SHALL assemble final document context from authoritative SQLite chunks with neighbor expansion, overlap merging, and duplicate suppression.

#### Scenario: Short text chunks expand with neighbors
- **WHEN** a selected text chunk is shorter than `CONTEXT_SHORT_CHUNK_MIN_CHARS`
- **THEN** context assembly may include previous and next sibling chunk text from the same document until the expanded text reaches the configured minimum or the configured maximum length

#### Scenario: Expanded context remains bounded
- **WHEN** neighbor expansion is applied
- **THEN** the expanded context for one candidate does not exceed `CONTEXT_EXPANDED_CHUNK_MAX_CHARS`

#### Scenario: Duplicate and overlapping context is removed
- **WHEN** multiple selected candidates produce identical or substantially overlapping context from the same document
- **THEN** final context includes the content once while preserving all matched child and neighbor ids in metadata

#### Scenario: Source metadata survives context assembly
- **WHEN** final context is assembled
- **THEN** every context item preserves document id, parent id, matched child ids, expanded neighbor ids, chunk type, title path, page range, and source file metadata when available

### Requirement: Document retrieval strategy is configurable
The system SHALL expose document retrieval strategy parameters through backend configuration with safe defaults.

#### Scenario: Defaults are applied when unset
- **WHEN** retrieval strategy environment or YAML values are absent
- **THEN** the backend starts with safe defaults for RRF, rerank thresholds, direct-load limits, and context expansion limits

#### Scenario: Configured strategy values are used
- **WHEN** retrieval strategy values are set through environment variables or YAML configuration
- **THEN** retrieval uses those configured values for weighted RRF, rerank thresholding, direct-load limits, and context expansion

### Requirement: FAQ retrieval remains out of scope
The system SHALL NOT add FAQ-specific indexing, retrieval, negative-question filtering, or FAQ answer backfill as part of this change.

#### Scenario: Document knowledge base behavior changes do not require FAQ type support
- **WHEN** this change is implemented
- **THEN** existing document knowledge base retrieval is enhanced without requiring `KnowledgeBaseType` to include FAQ
