## ADDED Requirements

### Requirement: Weknora-like knowledge-base creation wizard
The frontend SHALL provide a focused knowledge-base creation flow that mirrors Weknora's configuration structure while preserving Bee branding and only enabling supported options.

#### Scenario: Open creation wizard
- **WHEN** the user opens the create-knowledge-base action from the knowledge catalog
- **THEN** the UI SHALL show a modal or drawer with a left configuration rail and a main content area for basic information

#### Scenario: Enter basic information
- **WHEN** the user enters a valid name, optional description, and chooses the Document knowledge-base type
- **THEN** the create action SHALL submit a document-type knowledge base and navigate to its scoped detail workspace after success

#### Scenario: Unsupported knowledge-base type
- **WHEN** the user sees FAQ, Wiki, or future knowledge-base types that the backend does not support
- **THEN** the UI SHALL show those types as disabled or unavailable and SHALL NOT submit them as active create requests

### Requirement: Creation configuration sections
The creation wizard SHALL expose the same high-level configuration groups that users expect from WeKnora: basic information, model configuration, vector storage, parser engine, chunk settings, image/OCR handling, audio handling, knowledge graph, and advanced settings.

#### Scenario: Display configuration rail
- **WHEN** the creation wizard is open
- **THEN** the left rail SHALL list configuration sections in a stable order and highlight the currently active section

#### Scenario: Runtime unsupported section
- **WHEN** a configuration section maps to a feature that is not available in Bee's current backend
- **THEN** the section SHALL be marked disabled, read-only, or "not available" and SHALL NOT imply that the setting will take effect

#### Scenario: Submit requested and effective options
- **WHEN** the user submits supported index or provider options
- **THEN** the backend SHALL persist requested configuration and return effective configuration so the UI can display inactive overrides honestly

### Requirement: Creation validation and recovery
The creation wizard SHALL preserve user input and show actionable validation errors when creation fails.

#### Scenario: Empty name
- **WHEN** the user submits the wizard without a non-empty knowledge-base name
- **THEN** the UI SHALL block submission and show a validation message without closing the wizard

#### Scenario: Duplicate name rejected by backend
- **WHEN** the backend rejects a duplicate knowledge-base name
- **THEN** the UI SHALL keep the entered values visible and show the backend validation error

#### Scenario: Network or server failure
- **WHEN** creation fails because the API request fails
- **THEN** the UI SHALL keep the wizard open and allow the user to retry without re-entering all fields

### Requirement: Knowledge catalog integration
The catalog SHALL keep the WeKnora-like information architecture for active, favorite, recent, and workspace-scoped knowledge bases.

#### Scenario: Created knowledge base appears in catalog
- **WHEN** a new knowledge base is created successfully
- **THEN** the catalog SHALL refresh and include the new card with name, description, type, status, and aggregate counts

#### Scenario: Bee branding preserved
- **WHEN** the user views the knowledge catalog or creation wizard
- **THEN** the UI SHALL use Bee product naming and SHALL NOT display WeKnora logos, product names, or copied brand text
