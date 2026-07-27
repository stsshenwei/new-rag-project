## ADDED Requirements

### Requirement: Config-Gated Extended Tools
The agent runtime SHALL register extended non-wiki tools only when their feature flags and provider configuration are enabled.

#### Scenario: Web tools disabled
- **WHEN** the agent asks for web search while web tools are disabled
- **THEN** the tool returns a stable unavailable observation and the agent run continues safely

### Requirement: Web Search And Fetch Tools
The agent runtime SHALL support web search and web fetch tools behind explicit configuration with allowlists, timeouts, output limits, and sanitized trace records.

#### Scenario: Web fetch returns content
- **WHEN** an enabled web fetch tool retrieves a page
- **THEN** the observation contains bounded extracted content and the trace excludes cookies, secrets, and raw network internals

### Requirement: Data Analysis And Database Query Boundaries
The agent runtime SHALL expose data analysis and database query tools only through safe bounded adapters with explicit data source scope and read-only defaults.

#### Scenario: Database query outside scope
- **WHEN** an agent requests a database query against an unapproved data source
- **THEN** the tool rejects the call with an unavailable or unauthorized observation

### Requirement: Skill Execution Boundary
The agent runtime SHALL distinguish read-only skill loading from executable skill scripts and SHALL keep executable skill behavior disabled unless a secure sandbox is explicitly implemented.

#### Scenario: Agent requests executable skill
- **WHEN** executable skill support is not enabled
- **THEN** the runtime returns a clear unavailable observation instead of running local code

### Requirement: Tool Span Integration
Every agent tool call SHALL emit sanitized trace events and backend spans with tool name, bounded arguments, status, duration, error class, and output summary.

#### Scenario: Tool call fails
- **WHEN** a tool raises a recoverable error
- **THEN** the runtime records a failed tool span, emits a safe observation with retry guidance, and continues within max-iteration limits

