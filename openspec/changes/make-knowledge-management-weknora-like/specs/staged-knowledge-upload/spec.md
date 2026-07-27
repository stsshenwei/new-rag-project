## ADDED Requirements

### Requirement: Pending upload queue
The frontend SHALL let users select files or folders into a pending upload queue before any parsing, embedding, indexing, or enrichment starts.

#### Scenario: Select files
- **WHEN** the user selects one or more supported files
- **THEN** the UI SHALL add them to a pending queue showing name, relative path, size, type, and removable status

#### Scenario: Select folder
- **WHEN** the user selects a folder and the browser provides relative paths
- **THEN** the UI SHALL preserve safe folder-relative paths in the pending queue

#### Scenario: Remove pending file
- **WHEN** the user removes a pending file before confirmation
- **THEN** that file SHALL NOT be uploaded or processed

#### Scenario: Cancel pending queue
- **WHEN** the user cancels the pending upload dialog
- **THEN** no pending file SHALL be parsed, embedded, indexed, or enriched

### Requirement: Upload confirmation dialog
The frontend SHALL show a Weknora-like upload confirmation dialog before processing a batch.

#### Scenario: Show selected file count
- **WHEN** the confirmation dialog opens
- **THEN** it SHALL show the pending file count and a scrollable list of pending files

#### Scenario: Configure parser and chunking
- **WHEN** the dialog is open
- **THEN** it SHALL show parser engine and chunking settings with defaults derived from the selected knowledge base or runtime configuration

#### Scenario: Configure optional processing
- **WHEN** optional processing features such as question generation, graph extraction, OCR, multimodal, or audio handling are not available
- **THEN** the dialog SHALL show them disabled or unavailable and SHALL NOT submit them as enabled effective settings

#### Scenario: Confirm upload
- **WHEN** the user confirms the upload batch
- **THEN** the frontend SHALL create or confirm a scoped upload batch and begin file transfer and processing for the active knowledge base

### Requirement: Staged upload backend API
The backend SHALL support staged upload batches scoped to a single active knowledge base.

#### Scenario: Create batch
- **WHEN** the frontend creates an upload batch for an active knowledge base
- **THEN** the backend SHALL persist a batch with workspace ID, knowledge-base ID, draft status, and requested settings

#### Scenario: Add file to batch
- **WHEN** the frontend uploads a file into a draft or uploading batch
- **THEN** the backend SHALL save the source file under a safe managed upload path and create a file task without parsing or indexing it yet

#### Scenario: Confirm batch processing
- **WHEN** the frontend confirms a batch
- **THEN** the backend SHALL transition the batch to processing and schedule or execute parse, chunk, index, and enrichment phases according to effective settings

#### Scenario: Reject archived knowledge base
- **WHEN** the frontend tries to create, upload to, or confirm a batch for an archived knowledge base
- **THEN** the backend SHALL reject the request without saving new files or tasks

### Requirement: Data-safety boundary
The staged workflow SHALL make provider-bound processing explicit.

#### Scenario: Files selected but not confirmed
- **WHEN** files are only in the pending queue or draft batch
- **THEN** the system SHALL NOT send parsed text, chunks, images, or embeddings input to any external provider

#### Scenario: User confirms processing
- **WHEN** the user confirms upload and processing
- **THEN** the UI SHALL make clear that parsing/indexing may use configured providers, and the backend MAY call those providers only after the batch is confirmed

### Requirement: Compatibility upload path
Existing single-file upload callers SHOULD continue to work, but the new knowledge management UI SHALL use the staged upload workflow.

#### Scenario: Legacy upload request
- **WHEN** an existing client calls the prior upload endpoint
- **THEN** the backend SHALL preserve compatible behavior or return a documented validation error without corrupting staged upload state

#### Scenario: New UI upload
- **WHEN** the user uploads from the knowledge management page
- **THEN** the frontend SHALL use staged batch endpoints and SHALL NOT call direct upload-as-indexing endpoints
