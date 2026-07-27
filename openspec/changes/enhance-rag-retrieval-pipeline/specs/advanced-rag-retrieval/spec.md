## ADDED Requirements

### Requirement: Deep Docling Parse Output

The system SHALL use a Docling-based parser path for supported rich document formats and SHALL preserve structured element metadata including element type, title path, page range, captions, table structure, figure references, available layout metadata, and parse provenance.

#### Scenario: Rich document parse preserves structure

- **WHEN** a PDF or DOCX document is parsed through the ingest pipeline
- **THEN** the parsed document contains typed elements with title paths, available page/layout metadata, and metadata indicating whether each element came from Docling, Docling OCR, or fallback parsing

#### Scenario: Fallback parse keeps contract

- **WHEN** Docling parsing fails for a supported document
- **THEN** the fallback parser still returns a valid parsed document using the same parsed element contract

### Requirement: Milvus Dense And BM25 Indexing

The system SHALL index searchable child, table, and OCR chunks into Milvus with dense embedding vectors and BM25/sparse-search text when Milvus BM25 is enabled.

#### Scenario: Ingest writes hybrid retrieval records

- **WHEN** a document is ingested and Milvus BM25 is enabled
- **THEN** each indexable chunk is written to Milvus with chunk id, document id, parent id, chunk type, source, title path, page range, dense embedding, and BM25/sparse-search text

#### Scenario: Milvus BM25 can be disabled

- **WHEN** Milvus BM25 is disabled by configuration
- **THEN** ingest and chat retrieval continue with dense vector retrieval and fallback keyword behavior

### Requirement: Hybrid Retrieval With Milvus Dense And BM25

The system SHALL retrieve candidates from both Milvus dense vector search and Milvus BM25/sparse search, merge them by chunk id, and preserve per-source scores before optional reranking.

#### Scenario: Candidate merge deduplicates matching chunks

- **WHEN** the same chunk is returned by both Milvus dense search and Milvus BM25/sparse search
- **THEN** the merged candidate list contains one candidate for that chunk with both vector and BM25 score metadata

#### Scenario: BM25-only match remains eligible

- **WHEN** Milvus BM25/sparse search returns a relevant keyword match that dense vector search does not return
- **THEN** the candidate remains eligible for reranking and final context selection

### Requirement: KeywordSearch Interface

The system SHALL provide a `KeywordSearch` interface with `index(chunks)`, `search(query, top_k, filters)`, and `delete_by_doc_id(doc_id)` methods, backed by Milvus built-in BM25/sparse retrieval.

#### Scenario: Keyword search returns traceable hits

- **WHEN** `KeywordSearch.search` returns results for a query
- **THEN** each result contains `chunk_id`, `doc_id`, `parent_id`, and `score`

#### Scenario: Keyword search uses Milvus BM25

- **WHEN** keyword search is enabled
- **THEN** keyword indexing and search use Milvus BM25/sparse fields

#### Scenario: Technical exact terms are keyword-recallable

- **WHEN** indexed chunks contain parameter names, error codes, version numbers, technical document names, or command-line snippets
- **THEN** keyword search can recall those chunks using the exact keyword text

#### Scenario: Keyword backend can delete a document

- **WHEN** `KeywordSearch.delete_by_doc_id` is called for a document id
- **THEN** keyword records for that document are removed without deleting unrelated documents

### Requirement: HybridRetriever Interface

The system SHALL provide a `HybridRetriever` with `retrieve(question, top_k, filters) -> List[RetrievedChunk]`.

#### Scenario: Hybrid retriever fuses dense and keyword results

- **WHEN** `HybridRetriever.retrieve` is called
- **THEN** it embeds the question, requests dense top 50, requests keyword top 50, fuses results with RRF or weighted score fusion, deduplicates by chunk id, and returns top 30 candidates for reranking by default

#### Scenario: RRF scoring is available

- **WHEN** RRF fusion is configured
- **THEN** each candidate contribution is scored using `1 / (k + rank)` with default `k = 60`

#### Scenario: Filters are forwarded

- **WHEN** `HybridRetriever.retrieve` receives `doc_ids` or filters
- **THEN** dense and keyword retrieval both apply the filters where supported

### Requirement: Optional Local-First Reranking

The system SHALL optionally rerank merged retrieval candidates before parent/table/OCR context assembly and SHALL use reranker order as the final relevance order when reranking is enabled.

#### Scenario: Reranker changes final ordering

- **WHEN** reranking is enabled and the reranker returns scores for merged candidates
- **THEN** final context candidates are ordered by reranker score before parent recall and source extraction

#### Scenario: Reranker failure falls back safely

- **WHEN** reranking is enabled but the reranker call fails or times out
- **THEN** retrieval falls back to the pre-rerank hybrid ordering and the chat request still completes

#### Scenario: Reranker disabled keeps hybrid ordering

- **WHEN** reranking is disabled
- **THEN** retrieval uses the merged hybrid ordering without loading a reranker model

### Requirement: ContextBuilder Parent Recall

The system SHALL provide a `ContextBuilder` with `build(question, reranked_chunks) -> BuiltContext`.

#### Scenario: Child hits expand to parent context

- **WHEN** reranked chunks reference child chunks with `parent_id`
- **THEN** the context builder loads the parent chunk and uses parent content for LLM context

#### Scenario: Duplicate parents are merged

- **WHEN** multiple matched child chunks belong to the same parent
- **THEN** the context includes that parent once and merges child reference information

#### Scenario: Context includes trace metadata

- **WHEN** context is built for the LLM
- **THEN** each selected parent context includes file name, title path, page range, parent content, and matched child summaries

#### Scenario: Context budget keeps highest ranked parents

- **WHEN** selected parent context exceeds the configured token limit
- **THEN** lower-scoring parents are dropped before higher-scoring parents

### Requirement: LLMProvider Structured Answer

The system SHALL provide an `LLMProvider` with `generate_answer(question, context) -> Answer`.

#### Scenario: Answer is grounded in context

- **WHEN** the LLM provider generates an answer
- **THEN** the prompt instructs the model to answer only from retrieved context and avoid fabricated sources

#### Scenario: Missing answer is explicit

- **WHEN** retrieved context does not contain enough information to answer
- **THEN** the answer says `根据已检索到的资料，无法确定`

#### Scenario: Structured answer includes citations

- **WHEN** an answer is returned
- **THEN** it includes `answer`, `citations`, `used_chunks`, `confidence`, and optionally `debug_info`

#### Scenario: Citation schema is traceable

- **WHEN** citations are returned
- **THEN** each citation includes `doc_id`, `file_name`, `chunk_id`, `parent_id`, `title_path`, `page_start`, `page_end`, and a quote or summary

### Requirement: RAG Query APIs

The system SHALL provide RAG-specific document and query APIs for upload, ingest, query, and delete workflows.

#### Scenario: Upload document API

- **WHEN** a client calls `POST /rag/documents/upload`
- **THEN** the API returns `doc_id` and `status`

#### Scenario: Ingest document API

- **WHEN** a client calls `POST /rag/documents/{doc_id}/ingest`
- **THEN** the API returns `doc_id`, `parse_status`, `chunk_count`, and `vector_count`

#### Scenario: Query API

- **WHEN** a client calls `POST /rag/query` with `question`, optional `doc_ids`, `top_k`, and `filters`
- **THEN** the API returns `answer`, `citations`, `used_chunks`, and optional `debug_info`

#### Scenario: Delete document API

- **WHEN** a client calls `DELETE /rag/documents/{doc_id}`
- **THEN** the system deletes the original file record, chunk table rows, vector index records, and keyword index records for that document

### Requirement: Retrieval Debug Info

The system SHALL optionally return retrieval debug information controlled by configuration.

#### Scenario: Debug info includes retrieval stages

- **WHEN** debug info is enabled for a query
- **THEN** the response includes `dense_results`, `bm25_results`, `fused_results`, `reranked_results`, `selected_parent_chunks`, and `final_context_token_count`

#### Scenario: Debug info can be disabled

- **WHEN** debug info is disabled
- **THEN** query responses omit internal retrieval debug details

### Requirement: YAML RAG Configuration

The system SHALL support a YAML RAG configuration file with environment-variable substitution for parser, embedding, Milvus vector/BM25 store, reranker, retrieval, context, and LLM settings.

#### Scenario: YAML config loads retrieval settings

- **WHEN** a RAG config file defines dense top K, keyword top K, fusion top K, rerank top K, and context max tokens
- **THEN** the backend initializes retrieval and context settings from that configuration

#### Scenario: YAML config supports provider settings

- **WHEN** a RAG config file defines embedding, Milvus vector/BM25 store, reranker, and LLM provider settings
- **THEN** the backend initializes those provider boundaries using resolved environment variable values

### Requirement: Structured Table Enhancement

The system SHALL treat tables as first-class chunks with structured cell metadata, captions, nearby explanatory text, deterministic summaries, retrieval text, and LLM-ready table context.

#### Scenario: Table chunk preserves original table context

- **WHEN** a document contains a table
- **THEN** the stored table chunk includes original Markdown or HTML table content, structured fields when available, caption or nearby text when available, and a table summary

#### Scenario: Table retrieval uses enriched text

- **WHEN** a user asks a question whose answer is inside or near a table
- **THEN** dense and BM25/sparse indexing use table title path, caption, summary, fields, nearby text, and table content as searchable text

### Requirement: Optional Docling-First OCR Extraction

The system SHALL optionally extract OCR or image text from document images or scanned pages and SHALL make that text searchable with source and page metadata when OCR is enabled.

#### Scenario: OCR text becomes searchable

- **WHEN** OCR is enabled and Docling or an available OCR path extracts readable image text
- **THEN** the OCR text is stored as parsed elements or chunks linked to the document source and page metadata, and the text is indexed for retrieval

#### Scenario: OCR disabled avoids OCR dependency

- **WHEN** OCR is disabled
- **THEN** the backend does not require OCR-specific model or binary dependencies to start

#### Scenario: OCR failure does not fail text parse

- **WHEN** OCR is enabled but OCR extraction fails for an image
- **THEN** the document parse continues for non-image content and records OCR failure metadata or logs for diagnosis

### Requirement: Retrieval Configuration

The system SHALL expose environment configuration for Milvus BM25 enablement/settings, reranker enablement/provider settings, OCR enablement/provider settings, candidate fan-out limits, and retrieval timeouts.

#### Scenario: Defaults support local development

- **WHEN** no Milvus BM25, reranker, or OCR configuration is provided
- **THEN** the backend can still start and run with disabled-safe defaults

#### Scenario: Configured services are used

- **WHEN** Milvus BM25, reranker, or OCR settings are provided
- **THEN** the backend initializes the corresponding behavior using those settings

### Requirement: Source Traceability

The system SHALL retain source, document id, chunk id, parent id, chunk type, title path, and page metadata through parse, indexing, retrieval, reranking, and final source extraction.

#### Scenario: Final source includes trace metadata

- **WHEN** a retrieved answer uses parent, table, or OCR-derived context
- **THEN** the corresponding source metadata can be traced back to the original document, chunk, title path, and page range when available
