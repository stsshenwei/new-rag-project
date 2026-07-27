## ADDED Requirements

### Requirement: Evaluation runner
The system SHALL provide an evaluation runner that executes evaluation cases through the existing backend query path.

#### Scenario: Execute case through query service
- **WHEN** an evaluation run executes a case
- **THEN** the runner SHALL call the configured query path and capture the returned answer, citations, used chunks, used entities, graph paths, confidence, agent trace, tool calls, evidence summary, and debug metadata.

#### Scenario: Continue after case failure
- **WHEN** one evaluation case fails due to a query or scoring error
- **THEN** the runner SHALL record the case failure and continue executing remaining cases unless the run is cancelled.

### Requirement: Query snapshot capture
The system SHALL store a reproducible snapshot for every evaluation result.

#### Scenario: Capture result snapshot
- **WHEN** a case completes
- **THEN** the system SHALL store the case input, query configuration, response fields, latency in milliseconds, status, errors, and metric scores.

#### Scenario: Preserve agent trace safely
- **WHEN** an agentic response includes trace or tool call metadata
- **THEN** the evaluation snapshot SHALL store bounded public trace fields and SHALL NOT store hidden chain-of-thought, raw prompts, or memory context dumps.

### Requirement: Evaluation run lifecycle
The system SHALL track evaluation run lifecycle status.

#### Scenario: Start evaluation run
- **WHEN** an evaluation run is created
- **THEN** the system SHALL assign a run id and mark the run as running with started timestamp and dataset metadata.

#### Scenario: Finish evaluation run
- **WHEN** all selected cases finish
- **THEN** the system SHALL mark the run as completed, partial_failed, failed, or cancelled with finished timestamp and aggregate metadata.
