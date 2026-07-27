## ADDED Requirements

### Requirement: Durable Processing Task Queue
The system SHALL persist document processing tasks before returning from upload confirmation, including task type, scope, payload, status, attempt count, retry schedule, lease metadata, timestamps, and last error details.

#### Scenario: Confirmed upload creates durable tasks
- **WHEN** a user confirms an upload batch
- **THEN** the system creates durable processing task records for the batch documents before reporting that processing has started

#### Scenario: Restart recovers pending work
- **WHEN** the backend restarts while processing tasks are pending or leased past their deadline
- **THEN** the worker recovers runnable tasks and continues processing without requiring the user to re-upload files

### Requirement: Processing Retry And Dead Letter
The system SHALL retry transient processing failures according to per-stage retry policies and move exhausted tasks to a dead-letter store with task payload, error code, error message, attempt count, and trace id.

#### Scenario: Retryable parser failure
- **WHEN** a parser task fails with a retryable error
- **THEN** the system records the failure, increments the attempt count, schedules a retry, and keeps the document in a processing state

#### Scenario: Retry budget exhausted
- **WHEN** a task exceeds its retry budget
- **THEN** the system marks the task dead-lettered, records the final failure, and updates the document processing status to failed

### Requirement: Processing Cancellation
The system SHALL allow cancellation of queued, scheduled, retrying, and active processing tasks for a document or upload batch.

#### Scenario: Cancel queued document
- **WHEN** a user deletes or cancels a document with queued processing work
- **THEN** the system cancels pending tasks and prevents future processing writes for that document

#### Scenario: Cancel active document
- **WHEN** a user cancels a document while a worker is processing it
- **THEN** the worker observes cancellation before the next stage boundary and stops without indexing further derived evidence

### Requirement: Idempotent Processing Writes
Processing stages SHALL write documents, chunks, vectors, derived artifacts, and status updates idempotently for a document processing attempt.

#### Scenario: Retried indexing does not duplicate chunks
- **WHEN** an indexing stage is retried after a worker crash
- **THEN** the system replaces or reuses deterministic chunk/vector identifiers rather than creating duplicate retrievable evidence

