## ADDED Requirements

### Requirement: Upload Files From Knowledge Workspace
The system SHALL allow users to upload one supported file or multiple supported files from the knowledge workspace.

#### Scenario: Upload a single supported file
- **WHEN** the user selects one supported file from the knowledge workspace
- **THEN** the frontend uploads the file to the backend and the backend stores, parses, chunks, indexes, and returns document metadata for that file

#### Scenario: Upload multiple selected files
- **WHEN** the user selects multiple supported files from the knowledge workspace
- **THEN** the frontend creates one upload task containing all selected files and uploads each file independently

#### Scenario: Existing single-file upload contract remains valid
- **WHEN** an existing client posts `file` to `POST /documents/upload` without folder metadata
- **THEN** the backend accepts the request and stores the file under the uploads directory using the current single-file behavior

### Requirement: Upload Folders With Nested Relative Paths
The system SHALL allow users to upload a selected folder and SHALL preserve supported files' folder-relative paths when storing them.

#### Scenario: Upload a nested folder
- **WHEN** the user selects a folder containing supported files in nested subdirectories
- **THEN** the frontend submits each supported file with its folder-relative path and a shared upload batch identifier

#### Scenario: Store nested uploaded file
- **WHEN** the backend receives an uploaded file with a safe relative path and batch identifier
- **THEN** it stores the file under `backend/data/uploads/<batch>/<relative_path>` and records the stored source relative to `RAG_DATA_DIR`

#### Scenario: Source path preserves hierarchy
- **WHEN** a nested uploaded file is listed in the knowledge base or used as a citation source
- **THEN** its source path includes the preserved upload batch and nested folder hierarchy

### Requirement: Reject Unsafe Upload Paths
The system SHALL validate client-provided upload paths before writing files to disk.

#### Scenario: Reject path traversal
- **WHEN** an upload request includes a relative path with a `..` segment
- **THEN** the backend rejects the file and does not write it outside the uploads directory

#### Scenario: Reject absolute paths
- **WHEN** an upload request includes an absolute path or Windows drive-qualified path
- **THEN** the backend rejects the file and does not write it to disk

#### Scenario: Sanitize safe path segments
- **WHEN** an upload request includes a safe nested relative path with spaces, Chinese characters, or technical filename characters
- **THEN** the backend preserves a readable sanitized path and ensures the resolved target remains under the uploads directory

#### Scenario: Reject unsupported extension
- **WHEN** an upload request includes a file whose extension is not in the supported document extensions
- **THEN** the backend rejects that file without parsing or indexing it

### Requirement: Show Upload Task Progress
The system SHALL show a dedicated upload task workspace with total progress and per-file status.

#### Scenario: Display total progress
- **WHEN** an upload task contains multiple files
- **THEN** the frontend displays completed file count, total file count, and a progress indicator for the task

#### Scenario: Display current file
- **WHEN** a file is currently uploading or parsing
- **THEN** the frontend displays that file's relative path as the current active file

#### Scenario: Display per-file status
- **WHEN** files in an upload task are queued, uploading, parsing, parsed, or failed
- **THEN** the frontend displays each file with its relative path, size, status, and any returned chunk count or error message

#### Scenario: Refresh documents after completion
- **WHEN** all files in an upload task have reached parsed or failed status
- **THEN** the frontend refreshes the knowledge-base document list

### Requirement: Allow Partial Upload Success
The system SHALL continue processing remaining files in an upload task when one file fails validation, upload, parse, or index.

#### Scenario: One file fails validation
- **WHEN** one selected file is unsupported or has invalid path metadata
- **THEN** the frontend marks that file as failed and continues processing other files in the upload task

#### Scenario: One file fails parsing
- **WHEN** the backend fails to parse or index one uploaded file
- **THEN** the frontend marks that file as failed with the returned error and continues processing other files in the upload task

#### Scenario: Upload summary includes failures
- **WHEN** an upload task completes with both parsed and failed files
- **THEN** the frontend displays counts for successful and failed files

### Requirement: Preserve Existing Document Preview And Listing Behavior
The system SHALL keep uploaded documents compatible with the existing document list, content preview, PDF preview, and retrieval source behavior.

#### Scenario: Preview uploaded nested document
- **WHEN** the user opens a nested uploaded document from the knowledge list
- **THEN** the existing document preview endpoints resolve the stored source path safely and return the document content or file response

#### Scenario: Retrieve from uploaded nested document
- **WHEN** an uploaded nested document has been parsed and indexed
- **THEN** chat retrieval can use its chunks and source extraction can trace answers back to the stored nested source path

### Requirement: Delete Documents From Knowledge Workspace
The system SHALL allow users to delete a document from the knowledge workspace and SHALL remove the source file, metadata records, chunks, and vector index entries for that document.

#### Scenario: Confirm document deletion
- **WHEN** the user clicks delete for a document row in the knowledge workspace
- **THEN** the frontend asks for confirmation before calling the delete API

#### Scenario: Delete document successfully
- **WHEN** the user confirms deletion for a document
- **THEN** the frontend calls `DELETE /rag/documents/{doc_id}` and refreshes the knowledge-base document list after success

#### Scenario: Delete document failure
- **WHEN** the delete API returns an error
- **THEN** the frontend displays a delete error and keeps the document row visible
