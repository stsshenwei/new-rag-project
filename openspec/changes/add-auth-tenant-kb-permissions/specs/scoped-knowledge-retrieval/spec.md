## ADDED Requirements

### Requirement: Reuse authoritative knowledge ownership
The system SHALL authorize access through the existing workspace and knowledge-base ownership created by `add-multi-knowledge-base-domain`, without adding a second tenant ownership schema to documents or chunks.

#### Scenario: Uploaded document is scoped
- **WHEN** a user uploads a document into a knowledge base
- **THEN** the existing ingest service SHALL store the document under the active workspace and knowledge base, while the auth layer SHALL authorize the principal for that knowledge base.

#### Scenario: Parsed chunks inherit document scope
- **WHEN** a scoped document is parsed into chunks
- **THEN** every generated chunk SHALL inherit the existing document workspace and knowledge-base identity, and no auth-side backfill SHALL run.

#### Scenario: Prerequisite storage is not final
- **WHEN** knowledge storage reports `reset_required` or maintenance
- **THEN** authentication initialization SHALL fail closed and SHALL NOT migrate, backfill, or rewrite evidence ownership.

### Requirement: Scoped document APIs
The system SHALL enforce the active permission scope on document APIs.

#### Scenario: Document list is filtered
- **WHEN** a user lists documents
- **THEN** the system SHALL return only documents inside knowledge bases allowed by the active permission scope.

#### Scenario: Document content is filtered
- **WHEN** a user requests document content or a document file
- **THEN** the system SHALL return the content only if the document is inside the active permission scope.

#### Scenario: Unauthorized document access is forbidden
- **WHEN** a user requests a document outside the active permission scope
- **THEN** the system SHALL reject the request as forbidden.

#### Scenario: Document delete is role checked
- **WHEN** a user deletes a document
- **THEN** the system SHALL allow the deletion only if the user has editor or owner access to the document knowledge base.

### Requirement: Scoped keyword search
The system SHALL filter SQLite FTS5 keyword search by the active permission scope.

#### Scenario: Keyword search uses scope filters
- **WHEN** keyword search runs for a query
- **THEN** the system SHALL join FTS5 results to authoritative chunk rows and filter by the authorized workspace id, knowledge base ids, and allowed document ids.

#### Scenario: Unauthorized keyword hit is excluded
- **WHEN** an FTS5 match belongs to a document outside the active permission scope
- **THEN** the system SHALL exclude that hit from evidence results.

### Requirement: Scoped vector retrieval
The system SHALL filter Milvus dense and BM25 retrieval by the active permission scope.

#### Scenario: Vector rows reuse scope metadata
- **WHEN** chunks are written to the Milvus chunk vector collection
- **THEN** each row SHALL retain the existing workspace and knowledge-base metadata defined by the prerequisite change; the auth layer SHALL NOT add duplicate ownership fields.

#### Scenario: Dense retrieval uses scope expression
- **WHEN** dense vector retrieval runs
- **THEN** the Milvus query SHALL filter candidates by the authorized workspace id, allowed knowledge base ids, and allowed document ids.

#### Scenario: Milvus BM25 retrieval uses scope expression
- **WHEN** Milvus BM25 retrieval runs
- **THEN** the Milvus query SHALL filter candidates by the authorized workspace id, allowed knowledge base ids, and allowed document ids.

#### Scenario: Missing scope fields fail closed
- **WHEN** authentication is enabled and the prerequisite Milvus collection lacks workspace or knowledge-base fields
- **THEN** the system SHALL preserve `reset_required` and fail retrieval instead of running an unscoped query or performing an auth-side reindex.

### Requirement: Scoped graph retrieval
The system SHALL enforce permission scope on graph evidence returned by GraphRetriever.

#### Scenario: Entity search respects source evidence scope
- **WHEN** GraphRetriever returns entities with source chunks or relations
- **THEN** the system SHALL include only entities whose supporting source chunks are visible in the active permission scope.

#### Scenario: Neighbor search validates relation source chunks
- **WHEN** GraphRetriever returns neighbor relations
- **THEN** each relation SHALL be included only if its `source_chunk_id` belongs to a visible chunk in the active permission scope.

#### Scenario: Path search validates every edge
- **WHEN** GraphRetriever returns a graph path
- **THEN** the path SHALL be included only if every relation in the path has a `source_chunk_id` visible in the active permission scope.

#### Scenario: Unauthorized graph path is excluded
- **WHEN** any relation in a graph path points to an unauthorized chunk
- **THEN** the system SHALL exclude the path and record the exclusion reason in debug metadata.

### Requirement: Scoped agentic retrieval
The system SHALL pass the active permission scope through the finite-state Agent workflow and all approved retrieval tools.

#### Scenario: Permission step resolves scope
- **WHEN** the Agent workflow reaches `CheckPermissionScope`
- **THEN** the workflow SHALL resolve and record the active tenant, allowed knowledge bases, requested filters, and compatibility-mode status without exposing secrets.

#### Scenario: Tools receive scope
- **WHEN** the Agent workflow runs Raw RAG, Keyword Search, or GraphRetriever tools
- **THEN** each tool SHALL receive and enforce the same active permission scope.

#### Scenario: No accessible evidence returns insufficient answer
- **WHEN** retrieval finds no visible evidence inside the active permission scope
- **THEN** the system SHALL return an evidence-insufficient answer instead of using unauthorized evidence.

### Requirement: Scoped citations
The system SHALL verify citations and graph paths against the active permission scope before returning an answer.

#### Scenario: Citation verifier checks scope
- **WHEN** citation verification runs
- **THEN** each citation SHALL be accepted only if its chunk exists and is visible in the active permission scope.

#### Scenario: Graph source chunks are verified
- **WHEN** an answer includes graph paths
- **THEN** every graph relation source chunk SHALL be verified against the active permission scope.

#### Scenario: Invalid scoped citation blocks answer
- **WHEN** a generated answer references a citation outside the active permission scope
- **THEN** the system SHALL remove the citation and return an evidence-insufficient or citation-verification-failed answer.
