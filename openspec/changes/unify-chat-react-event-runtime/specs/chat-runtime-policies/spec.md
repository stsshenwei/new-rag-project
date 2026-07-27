## ADDED Requirements

### Requirement: Policy-Based Mode Selection
The system SHALL select chat behavior through an explicit runtime policy derived from the resolved chat mode.

#### Scenario: Quick policy selected
- **WHEN** the resolved chat mode is quick
- **THEN** the runtime SHALL use the quick policy's prompt, tool allowlist, iteration limit, retrieval posture, and completion rules

#### Scenario: Reasoning policy selected
- **WHEN** the resolved chat mode is reasoning
- **THEN** the runtime SHALL use the reasoning policy's prompt, tool allowlist, iteration limit, retrieval posture, and completion rules

### Requirement: Tool Allowlist Enforcement
The runtime SHALL expose and execute only tools allowed by the active policy and global runtime configuration.

#### Scenario: Tool not allowed by policy
- **WHEN** the model requests a tool that is not enabled for the active policy
- **THEN** the runtime SHALL reject the call with a sanitized tool result and SHALL NOT execute the tool

#### Scenario: Tool allowed by policy
- **WHEN** the model requests a registered tool allowed by the active policy
- **THEN** the runtime SHALL validate arguments, execute the tool, and append the sanitized observation to the message history

### Requirement: Prompt Strategy Per Policy
The runtime SHALL render policy-specific system prompts and context prompts without hardcoding behavior in the route handler.

#### Scenario: Quick prompt
- **WHEN** quick policy renders the model prompt
- **THEN** the prompt SHALL favor direct evidence-grounded answering and concise Markdown output without encouraging multi-step tool use

#### Scenario: Reasoning prompt
- **WHEN** reasoning policy renders the model prompt
- **THEN** the prompt SHALL favor ReAct-style retrieval, deep reading, public reflection, and evidence-grounded final synthesis

### Requirement: Policy Configuration
Runtime policies SHALL be configurable with safe defaults.

#### Scenario: Missing environment overrides
- **WHEN** no policy-specific environment overrides are configured
- **THEN** quick policy SHALL default to low iteration limits and reasoning policy SHALL default to bounded multi-iteration limits

#### Scenario: Invalid environment override
- **WHEN** a policy setting is invalid or unsafe
- **THEN** the backend SHALL fall back to a safe default and avoid enabling unrestricted tool access
