## ADDED Requirements

### Requirement: Query Understanding Before Retrieval
The system SHALL run a query-understanding stage before dense vector retrieval, keyword retrieval, parent recall, and answer generation when query understanding is enabled.

#### Scenario: Understand query before search
- **WHEN** a user asks a question and query understanding is enabled
- **THEN** the backend produces a query-understanding result before running dense or keyword retrieval

#### Scenario: Preserve raw-query fallback
- **WHEN** query understanding is disabled
- **THEN** the backend retrieves using the raw user question as it did before this change

#### Scenario: Understanding failure falls back
- **WHEN** query understanding raises an error or returns invalid output
- **THEN** the backend retrieves using the raw user question and the request still completes

### Requirement: Domain Terminology Normalization
The system SHALL normalize configured domain terminology and aliases into canonical terms for retrieval.

#### Scenario: Normalize electric port terminology
- **WHEN** the user query contains `电口` and the terminology dictionary maps `电口` to canonical `RJ-45`
- **THEN** the query-understanding result includes `RJ-45` in the normalized query, expanded terms, or retrieval queries

#### Scenario: Include aliases in expanded terms
- **WHEN** a terminology dictionary entry defines aliases for a matched term
- **THEN** the query-understanding result includes the canonical term and aliases in expanded terms or retrieval queries

#### Scenario: Record applied terminology
- **WHEN** a terminology dictionary entry is applied to a query
- **THEN** the query-understanding result records the original term and canonical term in applied terminology metadata

### Requirement: Multi-Query Retrieval
The system SHALL retrieve using the raw query plus normalized or expanded retrieval queries and SHALL fuse duplicate results by chunk identity.

#### Scenario: Retrieve with expanded queries
- **WHEN** query understanding produces multiple retrieval queries
- **THEN** the backend runs retrieval using those query variants in addition to or including the raw query

#### Scenario: Deduplicate multi-query results
- **WHEN** multiple query variants return the same chunk
- **THEN** the fused candidate list contains that chunk once with merged score or trace metadata

#### Scenario: Cap retrieval query count
- **WHEN** query understanding produces more query variants than the configured maximum
- **THEN** the backend uses no more than the configured maximum number of retrieval queries

### Requirement: Optional LLM Query Rewrite
The system SHALL optionally use an LLM-based query rewrite provider to supplement dictionary-based query understanding.

#### Scenario: LLM rewrite disabled
- **WHEN** LLM query rewrite is disabled
- **THEN** the backend does not call the LLM for query rewriting and still uses dictionary-based understanding

#### Scenario: LLM rewrite adds query variants
- **WHEN** LLM query rewrite is enabled and returns valid rewrite output
- **THEN** the backend includes valid rewrite queries in the retrieval query set without removing dictionary-derived canonical terms

#### Scenario: Invalid LLM rewrite is ignored
- **WHEN** LLM query rewrite returns invalid JSON or unusable query variants
- **THEN** the backend ignores the rewrite output and continues with dictionary-derived or raw retrieval queries

### Requirement: Query Understanding Debug Info
The system SHALL expose query-understanding details in retrieval debug output when retrieval debug is enabled.

#### Scenario: Debug includes query understanding
- **WHEN** retrieval debug is enabled and query understanding runs
- **THEN** the response debug information includes the normalized query, retrieval queries, expanded terms, and applied terminology metadata

#### Scenario: Debug omitted when disabled
- **WHEN** retrieval debug is disabled
- **THEN** query-understanding internals are omitted from the response

### Requirement: Backwards-Compatible Chat And RAG APIs
The system SHALL preserve existing chat and RAG API request and response contracts while adding query understanding internally.

#### Scenario: Chat stream remains compatible
- **WHEN** a client calls `POST /chat/stream`
- **THEN** the SSE framing and client-visible stream contract remain unchanged

#### Scenario: RAG query remains compatible
- **WHEN** a client calls `POST /rag/query`
- **THEN** the existing response fields remain compatible and query-understanding details appear only inside optional debug information
