## ADDED Requirements

### Requirement: Format-aware parser engine registry
The system SHALL resolve a parser from an engine name and normalized file extension, and the `builtin` engine SHALL provide the supported default parser map.

#### Scenario: Builtin parser selected
- **WHEN** a supported document is processed without an explicit parser engine
- **THEN** the system SHALL select the matching parser registered under `builtin`

#### Scenario: Requested engine lacks the format
- **WHEN** a selected available engine does not support the document extension and `builtin` does
- **THEN** the system SHALL use the builtin parser and record the fallback reason

#### Scenario: Unsupported format
- **WHEN** neither the requested engine nor `builtin` supports the extension
- **THEN** the system SHALL reject processing with a structured unsupported-format error before indexing

### Requirement: Requested and effective parser provenance
Every parse result and durable processing task SHALL record the requested engine, effective engine, parser implementation, and any fallback warning.

#### Scenario: Requested parser succeeds
- **WHEN** the requested parser processes the document successfully
- **THEN** requested and effective engine SHALL match and no fallback warning SHALL be reported

#### Scenario: Parser fallback succeeds
- **WHEN** policy permits a fallback after the requested parser is unavailable or fails
- **THEN** the result SHALL identify the effective parser and expose a sanitized fallback reason

### Requirement: Parser capability and availability reporting
The backend SHALL expose registered engine formats, availability, effective configuration, and sanitized unavailability reasons to upload configuration and preview clients.

#### Scenario: Optional dependency missing
- **WHEN** an optional parser dependency or service is unavailable
- **THEN** the engine SHALL be reported unavailable without preventing backend startup when builtin processing remains available

### Requirement: Safe parser limits and errors
Parser execution SHALL enforce configured file-size, page-count, rendering, and resource limits and SHALL return stable error codes without indexing partial uncommitted output.

#### Scenario: Limit exceeded
- **WHEN** a document exceeds an enforced parser limit
- **THEN** the task SHALL fail with the matching structured error code and SHALL NOT create retrieval index rows

