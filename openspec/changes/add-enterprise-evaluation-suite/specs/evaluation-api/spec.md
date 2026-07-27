## ADDED Requirements

### Requirement: Evaluation run API or CLI
The system SHALL expose a controlled interface to start evaluation runs.

#### Scenario: Start run from dataset path
- **WHEN** an operator provides a valid evaluation dataset path
- **THEN** the system SHALL start an evaluation run and return the run id and initial status.

#### Scenario: Reject invalid dataset path
- **WHEN** an operator provides an invalid or unsafe dataset path
- **THEN** the system SHALL reject the request without reading outside allowed evaluation paths.

### Requirement: Evaluation inspection
The system SHALL expose interfaces for listing runs and inspecting run results.

#### Scenario: List evaluation runs
- **WHEN** an operator requests evaluation runs
- **THEN** the system SHALL return run metadata ordered by most recent update.

#### Scenario: Inspect run results
- **WHEN** an operator requests a specific run
- **THEN** the system SHALL return run metadata, aggregate scores, report links or paths, and result summaries.

### Requirement: Production isolation
The system SHALL keep evaluation operations separate from user-facing query and chat behavior.

#### Scenario: Run evaluation
- **WHEN** an evaluation run is executing
- **THEN** existing `/rag/query`, `/chat/stream`, ingest, feedback, memory, and document browsing behavior SHALL remain unchanged.
