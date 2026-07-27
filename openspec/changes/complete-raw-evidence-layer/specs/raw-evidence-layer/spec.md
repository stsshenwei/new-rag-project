## ADDED Requirements

### Requirement: Durable chunk evidence storage
The system SHALL use `document_chunk` as the durable source of truth for raw evidence chunks, including parent, child, table, and OCR chunks.

#### Scenario: Store parsed chunks
- **WHEN** a document is parsed and indexed
- **THEN** the system SHALL store all generated chunks in `document_chunk` with chunk id, document id, parent id, chunk type, title path, content, page range, token count, metadata, and created timestamp.

#### Scenario: Preserve parent recall boundary
- **WHEN** child, table, or OCR chunks are retrieved for a query
- **THEN** the system SHALL be able to recall the matching parent chunk from `document_chunk` for answer context.

### Requirement: SQLite FTS5 keyword index
The system SHALL maintain a SQLite FTS5 keyword index for indexable raw evidence chunks.

#### Scenario: Index retrieval chunks
- **WHEN** child, table, or OCR chunks are stored in `document_chunk`
- **THEN** the system SHALL add or replace corresponding FTS5 rows containing the chunk id, document id, parent id, title path, content, content markdown, page range, and chunk type needed for keyword retrieval.

#### Scenario: Exclude parent chunks from keyword search units
- **WHEN** parent chunks are stored in `document_chunk`
- **THEN** the system SHALL NOT index parent chunks as primary FTS5 search units unless a future change explicitly enables that behavior.

#### Scenario: Search exact terms
- **WHEN** a query contains an exact model name, API name, configuration key, error code, or other domain term present in an indexed chunk
- **THEN** SQLite FTS5 keyword retrieval SHALL return matching chunk hits ranked by keyword relevance.

### Requirement: FTS5 synchronization
The system SHALL keep the FTS5 keyword index synchronized with `document_chunk` mutations.

#### Scenario: Replace document chunks
- **WHEN** chunks for a document are replaced during upload, parse, feedback indexing, or single-document ingest
- **THEN** the system SHALL delete old FTS5 rows for that document and insert FTS5 rows for the new indexable chunks in the same repository update flow.

#### Scenario: Reset repository
- **WHEN** the repository is reset during full ingest
- **THEN** the system SHALL remove existing `document`, `document_chunk`, and FTS5 rows before rebuilding indexes.

#### Scenario: Delete document
- **WHEN** a document is deleted
- **THEN** the system SHALL delete the document row, its `document_chunk` rows, its FTS5 rows, and its vector rows from Milvus.

### Requirement: Provider boundaries for raw retrieval
The system SHALL expose raw retrieval through replaceable provider boundaries for vector and keyword search.

#### Scenario: Vector provider
- **WHEN** dense retrieval is requested
- **THEN** the system SHALL call a vector retrieval provider backed by the existing Milvus `rag_chunk_vectors` collection.

#### Scenario: Keyword provider
- **WHEN** keyword retrieval is requested and Milvus BM25 is disabled or unavailable
- **THEN** the system SHALL call a SQLite FTS5 keyword provider instead of scanning all chunks in Python.

#### Scenario: Common hit shape
- **WHEN** vector, Milvus BM25, or SQLite FTS5 retrieval returns hits
- **THEN** the system SHALL normalize hits to a common shape containing content or resolvable chunk metadata, score information, chunk id, document id, parent id, chunk type, title path, and page range.

### Requirement: Hybrid raw evidence retrieval
The system SHALL combine dense and keyword raw evidence hits without changing existing parent recall behavior.

#### Scenario: Fuse dense and keyword hits
- **WHEN** a query is processed by raw evidence retrieval
- **THEN** the system SHALL retrieve dense hits and keyword hits, fuse them by chunk identity, preserve matched retrieval query traces, and rank fused candidates before parent recall.

#### Scenario: Preserve Milvus BM25 option
- **WHEN** Milvus BM25 is enabled
- **THEN** the system MAY use Milvus BM25 for keyword hits while still preserving SQLite FTS5 as the fallback keyword provider when Milvus BM25 is disabled.

#### Scenario: Recall parent context
- **WHEN** fused hits contain child, table, or OCR chunk matches
- **THEN** the system SHALL build answer context from recalled parent/table/OCR evidence using `document_chunk` records.

### Requirement: Citation traceability
The system SHALL return citations and used chunk identifiers that can be resolved to raw evidence chunks.

#### Scenario: Citation identifiers
- **WHEN** `/rag/query` returns citations
- **THEN** each citation SHALL include `doc_id`, `chunk_id`, `parent_id`, `source`, `title_path`, `page_start`, and `page_end` when those values are available from the matched evidence.

#### Scenario: Used chunks resolve
- **WHEN** `/rag/query` returns `used_chunks`
- **THEN** every chunk id in `used_chunks` SHALL resolve to an existing `document_chunk` row at response time.

#### Scenario: Insufficient evidence
- **WHEN** raw evidence retrieval returns no usable evidence for a question
- **THEN** the generated answer SHALL clearly state that the system cannot determine the answer from available evidence instead of presenting an unsupported factual answer.

### Requirement: Future-compatible query response
The system SHALL keep `/rag/query` compatible with future graph and agent retrieval layers.

#### Scenario: Raw evidence response fields
- **WHEN** `/rag/query` returns a successful response
- **THEN** the response SHALL include `answer`, `citations`, `used_chunks`, `used_entities`, `graph_paths`, `confidence`, and `debug_info`.

#### Scenario: Empty graph fields during raw evidence phase
- **WHEN** the query is answered only by the Raw Evidence Layer
- **THEN** `used_entities` and `graph_paths` SHALL be empty lists.

#### Scenario: Retrieval confidence
- **WHEN** `/rag/query` returns evidence-backed results
- **THEN** `confidence` SHALL be a numeric retrieval confidence derived from selected evidence scores and SHALL be present even when debug output is disabled.

### Requirement: Existing behavior compatibility
The system SHALL preserve current non-graph RAG application behavior while completing the Raw Evidence Layer.

#### Scenario: Chat stream compatibility
- **WHEN** `/chat/stream` handles a chat request
- **THEN** the stream SHALL preserve existing `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` event behavior.

#### Scenario: Upload and parse compatibility
- **WHEN** users upload or parse supported documents
- **THEN** the existing upload and parse endpoints SHALL keep returning compatible responses while also updating raw evidence indexes.

#### Scenario: Feedback compatibility
- **WHEN** users submit corrected answer feedback
- **THEN** the system SHALL continue creating feedback knowledge content and SHALL index its chunks into Milvus and SQLite FTS5.
