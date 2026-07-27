## ADDED Requirements

### Requirement: Durable evaluation storage
The system SHALL store evaluation runs and results durably.

#### Scenario: Store run metadata
- **WHEN** an evaluation run is created or updated
- **THEN** the system SHALL persist run id, dataset id, dataset version, status, timestamps, configuration snapshot, aggregate scores, report paths, and error message.

#### Scenario: Store result metadata
- **WHEN** an evaluation case result is produced
- **THEN** the system SHALL persist case id, run id, status, answer snapshot, evidence snapshot, scores, latency, and error details.

### Requirement: Evaluation reports
The system SHALL generate JSON and Markdown reports for evaluation runs.

#### Scenario: Generate JSON report
- **WHEN** an evaluation run completes
- **THEN** the system SHALL be able to generate a JSON report containing run metadata, aggregate scores, and per-case results.

#### Scenario: Generate Markdown report
- **WHEN** an evaluation run completes
- **THEN** the system SHALL be able to generate a Markdown report summarizing aggregate scores, failed cases, regressions, and notable evidence failures.

### Requirement: Regression comparison
The system SHALL compare evaluation runs when a baseline run is provided.

#### Scenario: Compare against baseline
- **WHEN** a run is compared with a baseline run for the same dataset
- **THEN** the system SHALL report metric deltas, newly failed cases, fixed cases, and latency changes.
