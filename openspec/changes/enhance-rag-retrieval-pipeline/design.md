## Context

The backend currently has a structured RAG foundation:

- `DocumentParser` returns `ParsedDocument`.
- `DocumentChunker` creates parent, child, and table chunks.
- `DocumentRepository` stores documents and chunks in SQLite.
- `MilvusVectorStore` stores dense vectors for child/table chunks.
- `RAGService` orchestrates ingest, retrieval, parent recall, source extraction, feedback write-back, and streaming answer generation.

The desired next step is a clearer retrieval architecture with replaceable boundaries. Dense vector retrieval and keyword/BM25 retrieval should both use Milvus. Keyword retrieval moves behind a `KeywordSearch` abstraction, and the implementation target is Milvus built-in BM25/sparse retrieval. SQLite remains the authoritative business store.

```text
file/upload
  -> Docling deep parse
  -> optional Docling OCR/image-text extraction
  -> ParsedDocument(elements with structure + metadata)
  -> DocumentChunker(parent / child / table / ocr chunks)
  -> SQLite(document, document_chunk truth)
  -> SQLite(document, document_chunk truth)
  -> Milvus(dense embeddings + BM25/sparse text)
  -> KeywordSearch(Milvus BM25/sparse)
  -> HybridRetriever(dense top 50 + keyword top 50 + fusion)
  -> Reranker(optional top 30 -> top 5-8)
  -> ContextBuilder(parent recall + neighbors + token budget)
  -> LLMProvider(structured answer + citations)
  -> /rag/query and existing chat flow
```

## Goals / Non-Goals

**Goals:**

- Abstract keyword retrieval behind `KeywordSearch`.
- Implement keyword retrieval with Milvus built-in BM25/sparse search.
- Fuse vector and keyword retrieval through a dedicated `HybridRetriever`.
- Build LLM context through a dedicated `ContextBuilder`.
- Generate structured answers through a dedicated `LLMProvider`.
- Preserve richer Docling output, including table, figure, caption, page, and layout metadata where available.
- Keep SQLite as the source of truth for parsed documents and chunks.
- Add a reranker abstraction that is default-disabled and local-model-first.
- Add optional OCR that is default-disabled and initially prefers Docling's available OCR/image-text capabilities.
- Treat tables as first-class retrieval and context units.
- Add `/rag/*` APIs while preserving existing APIs during transition.

**Non-Goals:**

- Do not replace Milvus.
- Do not build a background job system in this change.
- Do not require OCR or reranker dependencies for the backend to start.
- Do not change frontend source rendering unless a separate UI change requests it.
- Do not manually edit persisted Milvus, Chroma, or SQLite data files.

## Decisions

### Decision 1: Extend Milvus Into A Hybrid Retrieval Store

The existing `MilvusVectorStore` should evolve into a hybrid retrieval boundary while keeping the current class name for this change. This preserves existing construction and test call sites while adding explicit dense, BM25/sparse, and document replacement methods.

Responsibilities:

- Create/load the Milvus collection.
- Store dense embedding vectors.
- Store BM25/sparse-search text for the same indexable chunks.
- Search dense vectors.
- Search BM25/sparse text.
- Reset/rebuild the collection during destructive reindex.
- Return normalized candidate records with `chunk_id`, `doc_id`, `parent_id`, `chunk_type`, title path, page range, source metadata, and score metadata.

Rationale:

- The project already depends on Milvus.
- Keeping dense and BM25 retrieval in one backend reduces deployment complexity.
- SQLite remains cleanly responsible for business metadata and full context payloads.

Alternatives considered:

- Add a separate search engine for BM25: stronger standalone search feature set, but unnecessary operational complexity for this project.
- Use SQLite FTS: lightweight, but weaker scaling and duplicates retrieval logic outside Milvus.
- Keep only simple SQLite keyword scanning: easiest, but not enough for enterprise PDFs, exact product terms, table fields, and short keyword queries.

### Decision 1A: KeywordSearch Uses Milvus Built-In BM25

Keyword retrieval should be isolated behind:

```text
KeywordSearch:
  - index(chunks)
  - search(query, top_k, filters)
  - delete_by_doc_id(doc_id)
```

The implementation SHALL use Milvus built-in BM25/sparse retrieval. It must return `chunk_id`, `doc_id`, `parent_id`, and `score` for each hit. The indexed text must preserve exact technical terms, parameter names, error codes, version numbers, and command-line snippets so they can be recalled by keyword search.

Rationale:

- Enterprise technical documents often ask for exact strings that dense retrieval can miss.
- Keeping keyword search behind an interface avoids coupling retrieval orchestration to Milvus call details.
- Using Milvus BM25 avoids adding a second search service.

### Decision 2: Keep SQLite As Truth And Milvus As Rebuildable Index

SQLite continues to own durable document/chunk records. Milvus stores retrieval projections derived from source files and SQLite chunks.

Each indexable Milvus record should include:

- primary id
- dense vector
- BM25/sparse-search text
- chunk id
- doc id
- parent id
- chunk type
- title path
- page start/end
- source/file metadata needed for retrieval display

Structured table/OCR details should stay in SQLite `metadata_json`, not only in Milvus metadata. Milvus may store enough metadata for search filtering and candidate traceability, but LLM context assembly should fetch authoritative content from SQLite.

### Decision 3: Retrieval Pipeline Uses Fan-Out, Merge, Then Rerank

Retrieval should move into a dedicated `HybridRetriever`:

```text
HybridRetriever:
  - retrieve(question, top_k, filters) -> list[RetrievedChunk]
```

Retrieval stages:

```text
question
  -> embed question
  -> vector search top 50
  -> KeywordSearch/Milvus BM25 top 50
  -> fuse with RRF or weighted score fusion
  -> deduplicate by chunk_id
  -> return top 30 RetrievedChunk candidates for reranker
```

RRF default:

```text
score = 1 / (k + rank)
default k = 60
```

- dense fan-out: 50
- keyword fan-out: 50
- fusion top K: 30
- merged candidate limit before rerank: 60
- reranker top N: 12
- final context top K: existing `TOP_K`

All limits should be environment-configurable.

### Decision 4: Reranker Is Local-First And Optional

Introduce `Reranker`:

```text
Reranker:
  - rerank(question, chunks, top_k) -> list[RetrievedChunk]
```

It should support at least:

- disabled/no-op provider
- configurable model name/provider
- local bge-reranker
- future jina-reranker, Qwen rerank, or other cross-encoder providers

Default behavior should rerank fused top 30 down to top 5-8 when enabled. The first production preference is local reranker, for example a bge-reranker family model, because it avoids sending candidate context to another remote service and keeps latency/cost predictable after model load.

Reranker must have:

- enable flag
- model name/path
- top-N limit
- timeout
- failure fallback to hybrid ordering

### Decision 5: Docling Deep Parse Normalizes Into Current Models

Do not introduce a separate document representation. Extend `ParsedElement.metadata` and `Chunk.metadata`.

Important metadata:

- parse source: `docling`, `docling_ocr`, `fallback`
- page range
- layout coordinates when available
- table headers/rows/cells
- caption
- figure/image references
- OCR confidence/provider when available
- nearby explanatory text

Fallback parser must still produce the same `ParsedDocument` contract.

### Decision 6: Tables Use Separate Retrieval Text And LLM Context

Table chunks should keep two views:

- Retrieval view: title path, caption, nearby text, fields, deterministic summary, and sampled row text.
- LLM view: caption, nearby text, original Markdown/HTML table, and optional summary.

This avoids flattening tables so aggressively that the LLM loses structure, while still making table content retrievable by both dense and BM25/sparse search.

### Decision 7: OCR Is Additive, Default-Off, And Docling-First

OCR should not be required for normal startup or ingest. When `OCR_ENABLED=false`, parsing should behave as normal.

When enabled:

- Try Docling's available OCR/image-text extraction first.
- Produce OCR elements/chunks only for non-empty text.
- Store page/source/confidence metadata when available.
- Do not fail the whole document if OCR fails and other text was parsed.
- Allow future provider expansion without changing `RAGService`.

### Decision 8: ContextBuilder Owns Parent-Child Recall

`HybridRetriever` and `Reranker` operate on retrieved child chunks. LLM context assembly should be owned by:

```text
ContextBuilder:
  - build(question, reranked_chunks) -> BuiltContext
```

Responsibilities:

- Query parent chunks by `child.parent_id`.
- Keep each parent once.
- Merge reference metadata when multiple children hit the same parent.
- Optionally include adjacent child chunks before/after the matched child.
- Include file name, title path, page range, parent content, and matched child summaries.
- Enforce final context token budget.
- If context is too long, keep higher rerank-score parents first.

### Decision 9: LLMProvider Owns Structured Answer Generation

LLM calls should move behind:

```text
LLMProvider:
  - generate_answer(question, context) -> Answer
```

The prompt must require the model to answer only from context, return "根据已检索到的资料，无法确定" when the context is insufficient, avoid fabricated sources, and cite file names, page ranges, and sections when possible.

Structured answer shape:

```text
Answer:
  - answer
  - citations
  - used_chunks
  - confidence
  - debug_info

Citation:
  - doc_id
  - file_name
  - chunk_id
  - parent_id
  - title_path
  - page_start
  - page_end
  - quote or summary
```

`debug_info` must be controlled by configuration.

### Decision 10: Add Explicit /rag APIs

Add or design these APIs while preserving existing endpoints during migration:

- `POST /rag/documents/upload` returns `doc_id` and `status`.
- `POST /rag/documents/{doc_id}/ingest` returns `doc_id`, `parse_status`, `chunk_count`, and `vector_count`.
- `POST /rag/query` accepts `question`, optional `doc_ids`, `top_k`, and `filters`; returns structured answer, citations, used chunks, and optional debug info.
- `DELETE /rag/documents/{doc_id}` deletes original file record, chunk table rows, vector index records, and keyword index records.

### Decision 11: Debug Info Is A First-Class Retrieval Artifact

When enabled, query responses should include:

- dense results
- keyword/BM25 results
- fused results
- reranked results
- selected parent chunks
- final context token count

This data must be safe to disable for production responses.

### Decision 12: YAML Configuration Complements Env Vars

Introduce a RAG configuration file that can still resolve environment variables:

```yaml
rag:
  parser:
    type: docling
  embedding:
    provider: qwen
    model: text-embedding-v3
    base_url: ${EMBEDDING_BASE_URL}
    api_key: ${EMBEDDING_API_KEY}
  vector_store:
    type: milvus
    url: ${MILVUS_URI}
    collection: rag_chunks
  keyword_search:
    type: milvus
    url: ${MILVUS_URI}
    index: rag_chunks
  reranker:
    enabled: true
    provider: bge
    model: bge-reranker-v2-m3
  retrieval:
    dense_top_k: 50
    keyword_top_k: 50
    fusion_top_k: 30
    rerank_top_k: 8
  context:
    max_tokens: 8000
    include_neighbor_chunks: true
  llm:
    provider: qwen
    model: qwen-plus
    base_url: ${LLM_BASE_URL}
    api_key: ${LLM_API_KEY}
```

## Risks / Trade-offs

- Milvus BM25/sparse support depends on Milvus and pymilvus versions -> use a Milvus 2.5-compatible server and `pymilvus==2.5.4` or newer with `FunctionType.BM25` and `DataType.SPARSE_FLOAT_VECTOR` support.
- Enabling BM25 on an existing dense-only collection requires a full reindex because `bm25_text` and `bm25_sparse` are schema fields.
- Hybrid score calibration is tricky -> preserve raw scores and let reranker become final ordering when enabled.
- Local reranker adds model size and warm-up latency -> keep default disabled, add timeout, and cap candidate count.
- Docling OCR quality and availability can vary by install -> keep OCR default disabled and record parse/OCR provenance.
- Table metadata can grow large -> store full structured data in SQLite JSON, but keep Milvus metadata lean.

## Migration Plan

1. Add config flags/YAML with disabled-safe defaults:
   - `KEYWORD_SEARCH_TYPE=milvus`
   - `DENSE_RECALL_TOP_N=50`
   - `KEYWORD_RECALL_TOP_N=50`
   - `FUSION_TOP_K=30`
   - `RERANKER_ENABLED=false`
   - `RERANKER_PROVIDER=local`
   - `OCR_ENABLED=false`
   - `OCR_PROVIDER=docling`
2. Add tests using fake hybrid store, fake reranker, and fake OCR/docling behavior.
3. Add `KeywordSearch` interface backed by Milvus BM25/sparse search.
4. Wire Milvus dense and Milvus BM25 records during ingest.
5. Add `HybridRetriever` with RRF fusion.
6. Add reranker, context builder, LLM provider, and structured answer path.
7. Deepen Docling metadata extraction.
8. Enhance table metadata and table retrieval/context text.
9. Add optional Docling-first OCR extraction.
10. Update docs and require reindex after enabling new Milvus schema.

Rollback strategy:

- Set `MILVUS_BM25_ENABLED=false`, `RERANKER_ENABLED=false`, and `OCR_ENABLED=false`.
- Reindex into the previous dense-only collection schema if schema compatibility requires it.
- Keep SQLite chunk content and metadata as the source for recovery.

## Open Questions

- Which local reranker model should be the first supported target in this environment?
- How much structured table data should be copied into Milvus metadata versus kept only in SQLite metadata JSON?
