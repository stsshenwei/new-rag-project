## ADDED Requirements

### Requirement: YAML Prompt Template Catalog
The system SHALL load agent system prompt templates from YAML configuration.

#### Scenario: Load default catalog
- **WHEN** the backend starts
- **THEN** it SHALL load a prompt template catalog containing at least `progressive_rag_agent` and `pure_agent`

#### Scenario: Missing catalog
- **WHEN** the configured prompt template file is missing or invalid
- **THEN** the backend SHALL fail fast with a clear startup error or fall back to a bundled safe default according to configuration

#### Scenario: Select template by id
- **WHEN** runtime configuration specifies an agent prompt template id
- **THEN** the runtime SHALL select that template if it exists and SHALL report a clear configuration error if it does not

### Requirement: Progressive RAG Prompt Behavior
The system SHALL provide an adapted progressive RAG prompt that preserves Weknora-style evidence-first behavior for document knowledge bases.

#### Scenario: Evidence-first instruction
- **WHEN** the runtime uses `progressive_rag_agent`
- **THEN** the system prompt SHALL instruct the model to answer factual domain questions from retrieved KB evidence rather than unsupported parametric knowledge

#### Scenario: Fresh retrieval per turn
- **WHEN** a new user question requires factual or domain-specific evidence
- **THEN** the system prompt SHALL instruct the model to perform fresh retrieval for that turn instead of relying only on previous retrieved content

#### Scenario: Knowledge-base priority
- **WHEN** configured non-KB tools are available in a later version
- **THEN** the prompt SHALL prioritize knowledge-base retrieval and deep reading before non-KB fallback tools

### Requirement: Placeholder Rendering
The system SHALL render prompt placeholders with safe runtime context.

#### Scenario: Bound knowledge bases rendered
- **WHEN** a reasoning request has one or more selected knowledge bases
- **THEN** the rendered prompt or user runtime context SHALL include bounded KB names, ids, types, capabilities, and recent document summaries in a structured block

#### Scenario: Skills metadata rendered
- **WHEN** runtime skills are enabled
- **THEN** the rendered prompt SHALL include only skill names and descriptions until the model calls `read_skill`

#### Scenario: Secrets excluded
- **WHEN** templates are rendered
- **THEN** the rendered prompt SHALL NOT include API keys, provider secrets, raw environment values, or hidden chain-of-thought

### Requirement: Prompt Confidentiality
The system SHALL instruct and enforce prompt confidentiality for agent runtime prompts.

#### Scenario: User asks for system prompt
- **WHEN** the user asks for the system prompt, tool instructions, or internal workflow
- **THEN** the agent SHALL refuse to reveal the prompt content and MAY only describe its high-level role

#### Scenario: Trace includes prompt metadata
- **WHEN** agent trace events are returned to the frontend
- **THEN** they SHALL NOT include raw system prompt text or raw rendered user prompt text

### Requirement: Template Compatibility
The system SHALL preserve existing chat behavior while adding templates.

#### Scenario: Runtime disabled
- **WHEN** the Weknora-style runtime is disabled
- **THEN** existing `SYSTEM_PROMPT` behavior for quick chat and deterministic reasoning SHALL remain compatible

#### Scenario: Runtime enabled
- **WHEN** the Weknora-style runtime is enabled
- **THEN** reasoning mode SHALL use the selected YAML template for agent system instructions
