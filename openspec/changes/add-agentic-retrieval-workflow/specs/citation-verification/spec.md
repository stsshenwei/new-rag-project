## ADDED Requirements

### Requirement: Citation verification
The system SHALL verify answer citations against raw evidence before returning factual answers.

#### Scenario: Citation resolves to document chunk
- **WHEN** an answer citation references a chunk
- **THEN** CitationVerifier SHALL verify that the chunk resolves through `DocumentRepository.get_chunk()`.

#### Scenario: Invalid citation blocks factual answer
- **WHEN** a factual answer has citations that cannot resolve to raw chunks
- **THEN** the workflow SHALL reject or downgrade the answer to an insufficient-evidence response.

### Requirement: Graph path verification
The system SHALL verify graph paths against raw source chunks before returning them as evidence.

#### Scenario: Graph path relation has source chunk
- **WHEN** a graph path is returned
- **THEN** every relation in the path SHALL contain a non-empty `source_chunk_id`.

#### Scenario: Graph path source chunk resolves
- **WHEN** a graph path relation contains `source_chunk_id`
- **THEN** CitationVerifier SHALL verify that the source chunk resolves through `DocumentRepository.get_chunk()`.

#### Scenario: Invalid graph path is excluded
- **WHEN** a graph path has a missing or unresolvable source chunk
- **THEN** the workflow SHALL exclude that graph path from usable evidence and record the exclusion in verification metadata.

### Requirement: Used evidence verification
The system SHALL verify used chunks and used entities before returning the enterprise response.

#### Scenario: Used chunks resolve
- **WHEN** `used_chunks` are returned
- **THEN** every used chunk id SHALL resolve to `document_chunk`.

#### Scenario: Verification result is traceable
- **WHEN** citation verification completes
- **THEN** the agent trace SHALL include a user-facing verification summary and debug metadata SHALL include verification details.
