## ADDED Requirements

### Requirement: Durable upload and processing task lifecycle
The backend SHALL persist upload batch and file task state for upload, parsing, indexing, enrichment, completion, cancellation, and failure.

#### Scenario: Batch lifecycle
- **WHEN** a batch moves from draft through processing to completion
- **THEN** the backend SHALL persist each externally visible status transition with timestamps

#### Scenario: File lifecycle
- **WHEN** a file is uploaded, parsed, indexed, enriched, or fails
- **THEN** the backend SHALL persist the file task status, document ID if available, chunk count if available, and a sanitized error message if failed

#### Scenario: Page refresh
- **WHEN** the user refreshes the browser during processing
- **THEN** the frontend SHALL reload the batch or current document statuses from backend state instead of losing all progress

### Requirement: Batch status API
The backend SHALL expose scoped status endpoints for upload batches and file tasks.

#### Scenario: Fetch batch status
- **WHEN** the frontend requests a batch by ID with the active knowledge-base ID
- **THEN** the backend SHALL return batch metadata, effective settings, file tasks, aggregate counts, and current status

#### Scenario: Cross-KB batch access
- **WHEN** a client requests a batch using a knowledge-base ID that does not own the batch
- **THEN** the backend SHALL reject or return not found and SHALL NOT reveal file names or errors from another knowledge base

#### Scenario: Poll active batch
- **WHEN** a batch is processing
- **THEN** the frontend SHALL poll or subscribe to status updates until the batch reaches a terminal state

### Requirement: Partial failure and retry
The task system SHALL allow partial success within a batch and targeted retry of failed files.

#### Scenario: One file fails
- **WHEN** one file in a batch fails parsing, indexing, or enrichment
- **THEN** the batch SHALL record partial failure while successfully processed files remain available in the knowledge base

#### Scenario: Retry failed file
- **WHEN** the user retries a failed file task
- **THEN** the backend SHALL rerun only the failed file's remaining processing phases within the same knowledge-base scope

#### Scenario: Retry does not duplicate document
- **WHEN** a retry succeeds after a prior partial document record exists
- **THEN** the backend SHALL update or replace the scoped document state without creating duplicate active documents for the same file task

### Requirement: Cancellation
The task system SHALL allow canceling draft, uploading, or queued batches without deleting unrelated knowledge-base content.

#### Scenario: Cancel draft batch
- **WHEN** the user cancels a draft batch before processing starts
- **THEN** the backend SHALL mark the batch canceled and SHALL NOT create document chunks or vector rows

#### Scenario: Cancel processing batch
- **WHEN** the user requests cancellation while a batch is processing
- **THEN** the backend SHALL stop processing files that have not started where possible and SHALL preserve already completed documents

### Requirement: Maintenance and reset awareness
Processing tasks SHALL respect storage reset and maintenance state.

#### Scenario: Reset required
- **WHEN** storage reports reset-required or maintenance state
- **THEN** the backend SHALL reject new upload batches and processing confirmations with a clear error

#### Scenario: Clean rebuild
- **WHEN** the destructive clean-rebuild CLI is executed with managed sources deletion
- **THEN** upload batch and file task records SHALL be removed or reinitialized consistently with document and source deletion
