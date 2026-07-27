## ADDED Requirements

### Requirement: Preloaded Runtime Skills
The system SHALL support preloaded read-only runtime skills for the chat agent.

#### Scenario: Discover skills
- **WHEN** runtime skills are enabled
- **THEN** the backend SHALL discover skill directories from the configured preloaded skills path and expose each skill's name and description to the agent prompt metadata

#### Scenario: Skills disabled
- **WHEN** runtime skills are disabled
- **THEN** the backend SHALL NOT expose `read_skill` to the model and SHALL NOT include skill metadata in rendered prompts

#### Scenario: Invalid skill metadata
- **WHEN** a skill lacks readable metadata or a skill instruction file
- **THEN** the backend SHALL skip that skill and log a warning without preventing startup

### Requirement: Read Skill Tool
The system SHALL provide a `read_skill` tool that loads full instructions for one configured preloaded skill.

#### Scenario: Read existing skill
- **WHEN** the model calls `read_skill` with a valid skill name
- **THEN** the tool SHALL return the skill instructions as bounded text and record a tool observation

#### Scenario: Read missing skill
- **WHEN** the model calls `read_skill` with an unknown skill name
- **THEN** the tool SHALL return a recoverable error observation and SHALL NOT access arbitrary filesystem paths

#### Scenario: Path traversal blocked
- **WHEN** the model passes a skill name or path containing traversal, absolute paths, or drive-qualified paths
- **THEN** the tool SHALL reject the request before reading from disk

### Requirement: Skill Priority Boundaries
The system SHALL treat runtime skills as lower priority than system prompts and safety rules.

#### Scenario: Skill conflicts with prompt
- **WHEN** loaded skill instructions conflict with evidence-first retrieval, prompt confidentiality, tenant isolation, or user-safe trace rules
- **THEN** the runtime SHALL follow the system prompt and safety rules over the skill

#### Scenario: Skill matched by user request
- **WHEN** the user request clearly matches an enabled skill's description
- **THEN** the prompt SHALL instruct the model to call `read_skill` before applying the skill in the final answer

### Requirement: Script Execution Deferred
The system SHALL NOT execute skill scripts in this change.

#### Scenario: Script execution requested
- **WHEN** the model attempts to call `execute_skill_script` or asks to run a skill script
- **THEN** the runtime SHALL report that executable skill scripts are unavailable in the current configuration

#### Scenario: Runtime tool list built
- **WHEN** the default runtime tool list is built
- **THEN** it SHALL NOT include `execute_skill_script`
