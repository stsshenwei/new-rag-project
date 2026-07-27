## ADDED Requirements

### Requirement: Rule-based metric scoring
The system SHALL compute deterministic rule-based metrics for each evaluation result.

#### Scenario: Score citation traceability
- **WHEN** a result includes citations or used chunks
- **THEN** the system SHALL score whether each referenced chunk can be resolved to `document_chunk`.

#### Scenario: Score expected source coverage
- **WHEN** a case defines expected source chunk ids or document ids
- **THEN** the system SHALL score whether the result used matching citations or chunks.

#### Scenario: Score expected answer terms
- **WHEN** a case defines expected answer terms
- **THEN** the system SHALL score whether the final answer contains the required terms using case-insensitive matching.

### Requirement: Graph and agent metrics
The system SHALL score graph path traceability and agent tool behavior when expectations are present.

#### Scenario: Score graph path traceability
- **WHEN** a result includes graph paths
- **THEN** the system SHALL score whether every graph relation has a resolvable `source_chunk_id`.

#### Scenario: Score expected tools
- **WHEN** a case defines expected tools or forbidden tools
- **THEN** the system SHALL score whether the agent tool calls match those expectations.

### Requirement: Insufficient evidence metric
The system SHALL verify expected insufficient-evidence behavior.

#### Scenario: Expected uncertainty
- **WHEN** a case is marked as expecting insufficient evidence
- **THEN** the system SHALL score the result as passing only if the answer clearly states that the system cannot determine the answer from available evidence.

### Requirement: Optional judge providers
The system SHALL define optional judge provider interfaces for semantic evaluation without requiring them for default runs.

#### Scenario: Judge provider disabled
- **WHEN** no judge provider is configured
- **THEN** the evaluation run SHALL still complete using rule-based metrics.

#### Scenario: Judge provider enabled
- **WHEN** a judge provider is configured
- **THEN** the system SHALL add judge scores and explanations to the result without replacing rule-based metric scores.
