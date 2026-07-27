## ADDED Requirements

### Requirement: Evaluation dataset format
The system SHALL support versioned evaluation datasets containing test cases for Raw RAG, GraphRAG, and Agentic Retrieval behavior.

#### Scenario: Load valid dataset
- **WHEN** an evaluation dataset file contains a supported schema version and valid cases
- **THEN** the system SHALL load the dataset with its id, name, version, metadata, and cases.

#### Scenario: Reject unsupported dataset schema
- **WHEN** an evaluation dataset file uses an unsupported schema version
- **THEN** the system SHALL reject the dataset with a validation error before executing any cases.

### Requirement: Evaluation case fields
The system SHALL allow each evaluation case to define question text, query type, tags, filters, expected answer terms, expected source chunks, expected entities, expected graph paths, expected tools, and insufficient-evidence expectations.

#### Scenario: Validate required case fields
- **WHEN** a case is missing an id or question
- **THEN** the system SHALL report the case as invalid and SHALL NOT execute it.

#### Scenario: Preserve optional expectations
- **WHEN** a case defines expected sources, entities, graph paths, tools, or answer terms
- **THEN** the system SHALL preserve those expectations for metric scoring.

### Requirement: Dataset isolation
The system SHALL keep evaluation datasets separate from the retrievable knowledge corpus.

#### Scenario: Load eval dataset
- **WHEN** an evaluation dataset is loaded
- **THEN** the system SHALL NOT add the dataset content to document ingest, vector indexes, FTS5 indexes, graph extraction, feedback files, or memory storage.
