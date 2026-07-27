## ADDED Requirements

### Requirement: Scoped document workspace
The frontend SHALL provide a document management workspace scoped to the selected active knowledge base.

#### Scenario: Open knowledge-base detail
- **WHEN** the user opens a knowledge-base card
- **THEN** the detail workspace SHALL load only documents and aggregate status for that knowledge base

#### Scenario: Archived knowledge base
- **WHEN** the selected knowledge base is archived
- **THEN** the workspace SHALL disable upload, processing, and retrieval-start actions while preserving read-only metadata where supported

### Requirement: Document toolbar filters
The document workspace SHALL provide a compact toolbar with search, tag filter, file-type filter, status filter, source filter, time range filter, refresh, and view-mode controls.

#### Scenario: Search documents
- **WHEN** the user enters a document search query
- **THEN** the frontend SHALL request or derive a document list filtered to matching names, paths, summaries, or supported metadata within the active knowledge base

#### Scenario: Filter by type and status
- **WHEN** the user selects file type or processing status filters
- **THEN** the document list SHALL show only documents matching those filters and SHALL NOT include documents from another knowledge base

#### Scenario: Filter by time range
- **WHEN** the user selects start and end times
- **THEN** the document list SHALL apply the time range to document creation or update time consistently and show the active range in the toolbar

### Requirement: Grid and list document views
The document workspace SHALL support a card/grid mode and a compact list mode without changing the selected knowledge-base scope.

#### Scenario: Grid mode
- **WHEN** the user chooses grid mode
- **THEN** documents SHALL render as compact cards with title, summary or preview, status, timestamp, file type, and action menu

#### Scenario: List mode
- **WHEN** the user chooses list mode
- **THEN** documents SHALL render in dense rows with stable columns for name, status, chunks, type, source, updated time, and actions

#### Scenario: View preference
- **WHEN** the user switches between grid and list mode
- **THEN** the UI SHALL preserve the active filters and SHALL NOT refetch from a different knowledge-base scope

### Requirement: Document actions and bulk selection
The workspace SHALL expose expected document actions without allowing cross-KB operations.

#### Scenario: Open document preview
- **WHEN** the user opens a document
- **THEN** the preview request SHALL include the document's knowledge-base ID and SHALL fail safely if the document is outside the active scope

#### Scenario: Delete document
- **WHEN** the user deletes a document
- **THEN** the UI SHALL require confirmation and call a scoped delete endpoint using the active knowledge-base ID

#### Scenario: Bulk action selection
- **WHEN** the user selects multiple documents
- **THEN** bulk actions SHALL operate only on selected documents in the active knowledge base and SHALL show partial failure details if any item fails

### Requirement: Upload action menu
The document workspace SHALL provide an upload action menu with document upload, folder upload, webpage import, and online editing entries.

#### Scenario: Supported upload entries
- **WHEN** the user opens the upload action menu
- **THEN** document upload and folder upload SHALL open the staged upload workflow for the active knowledge base

#### Scenario: Unsupported future entries
- **WHEN** webpage import or online editing are not implemented
- **THEN** the menu SHALL show them disabled or unavailable and SHALL NOT trigger hidden or partial backend behavior
