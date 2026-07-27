## ADDED Requirements

### Requirement: Document structure profiling
Before automatic chunking, the system SHALL profile Markdown headings, page breaks, numbered sections, multilingual chapter markers, all-caps headings, visual separators, repeated footer signals, tables, code, line statistics, and language hints.

#### Scenario: Structured Markdown profile
- **WHEN** a parsed document contains Markdown headings
- **THEN** the profile SHALL include heading counts by level, total heading density, and a deterministic dominant heading level

### Requirement: Adaptive strategy chain
The chunker SHALL support `auto`, `heading`, `heuristic`, and `recursive` strategies; automatic mode SHALL attempt eligible strategies in heading, heuristic, recursive order.

#### Scenario: Heading candidate
- **WHEN** a document has at least three Markdown headings, heading density above 0.5 percent, and a dominant level
- **THEN** `heading` SHALL be the first automatic strategy attempted

#### Scenario: Heuristic candidate
- **WHEN** heuristic markers total at least five or a page break or supported chapter marker exists
- **THEN** `heuristic` SHALL appear before recursive fallback

#### Scenario: Unstructured document
- **WHEN** no structural strategy is eligible
- **THEN** the system SHALL use recursive separator chunking

### Requirement: Strategy output validation and fallback
Every non-final strategy output SHALL be validated for empty output, ineffective single chunks, excessive tiny chunks, uniformly undersized chunks, and chunks over twice the target size; rejected tiers SHALL record reasons and fall through.

#### Scenario: Fragmented heading output
- **WHEN** heading chunking produces more than the allowed proportion of tiny chunks
- **THEN** the output SHALL be rejected and the next eligible strategy SHALL run

#### Scenario: Recursive final fallback
- **WHEN** all structural tiers are rejected
- **THEN** recursive chunking SHALL return the safe final result instead of returning no chunks

### Requirement: Recursive separator chunking
Recursive chunking SHALL apply ordered separators, recurse only on oversize pieces, align overlap to usable boundaries where possible, and use bounded hard splitting only as the final fallback.

#### Scenario: Chinese prose
- **WHEN** a paragraph remains oversized after newline separators
- **THEN** configured Chinese sentence punctuation SHALL be attempted before fixed-width splitting

### Requirement: Protected structural spans
Chunking SHALL protect configured formula, image, link, code, and table-row spans from ordinary boundaries while imposing a maximum protected-span safety limit.

#### Scenario: Boundary inside protected code
- **WHEN** a heading or heuristic marker appears inside a fenced code block
- **THEN** it SHALL NOT become a structural split boundary

#### Scenario: Table split across chunks
- **WHEN** a table cannot fit within one target chunk
- **THEN** rows SHALL remain intact where possible and subsequent table chunks SHALL retain the table header context

### Requirement: Adaptive parent-child chunking
When parent-child mode is enabled, the system SHALL chunk the document at the parent target and then independently chunk each parent at the child target using the effective adaptive strategy.

#### Scenario: Child retrieval and parent recall
- **WHEN** an indexed child chunk is retrieved
- **THEN** answer context SHALL be able to recall its parent while preserving child and parent provenance

#### Scenario: Identical single child
- **WHEN** a parent produces one child with identical content
- **THEN** the system SHALL avoid unnecessary duplicate active evidence while retaining retrievability

### Requirement: Stable chunk provenance
Each chunk SHALL carry document, page, title-path, parent, strategy, size-unit, content, and embedding-context provenance, with heading context stored separately from raw content.

#### Scenario: Heading-aware embedding
- **WHEN** a chunk has an active heading breadcrumb
- **THEN** embedding text SHALL include the breadcrumb while raw content and its source offsets SHALL remain unchanged

### Requirement: One-time complete legacy data reset
Before the new processing schema is activated, the system SHALL require an explicit maintenance operation that deletes the entire legacy SQLite database and all contained application records, every FTS table, all Milvus collections and vectors, legacy media resources, and all other derived processing state. The new application SHALL NOT migrate, read, query, or expose any legacy persisted data.

#### Scenario: Legacy schema detected at startup
- **WHEN** startup detects a legacy SQLite schema, legacy Milvus collection, or incomplete prior reset
- **THEN** the system SHALL enter `reset_required` maintenance state and SHALL NOT perform an implicit destructive reset

#### Scenario: Administrator confirms full reset
- **WHEN** an administrator runs the full-reset maintenance command and explicitly confirms the target environment and complete deletion scope
- **THEN** the system SHALL delete all legacy application, vector, FTS, media, authentication, tenant, knowledge, task, chat, memory, graph, and evaluation data before initializing an empty final schema

#### Scenario: Legacy data access after reset
- **WHEN** the new application starts after a successful full reset
- **THEN** no API, repository, compatibility adapter, or background process SHALL expose or consume legacy data
