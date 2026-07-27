## ADDED Requirements

### Requirement: ReAct Runtime Execution
The system SHALL provide a Weknora-style ReAct runtime for intelligent reasoning mode that alternates model tool selection, tool execution, observation appending, and final answer synthesis.

#### Scenario: Runtime executes multiple rounds
- **WHEN** reasoning mode uses the Weknora-style runtime for a factual knowledge-base question
- **THEN** the runtime SHALL call the chat model with tool definitions, execute requested tools, append observations, and continue until the model returns a final answer or the configured iteration limit is reached

#### Scenario: Quick mode remains unchanged
- **WHEN** a chat request uses `chat_mode` set to `quick`
- **THEN** the backend SHALL use the existing quick retrieval-answer path and SHALL NOT invoke the ReAct runtime

#### Scenario: Runtime unavailable
- **WHEN** reasoning mode is requested but the ReAct runtime is disabled or unavailable
- **THEN** the backend SHALL use the existing reasoning workflow fallback or return the existing explicit reasoning-unavailable error according to current configuration

### Requirement: Tool Registry
The system SHALL expose model-callable tools through a registry that provides stable function definitions, safe execution, validation, logging, and cleanup.

#### Scenario: Function definitions are stable
- **WHEN** the runtime builds the model request tools
- **THEN** the registry SHALL return tool definitions in stable sorted order with name, description, and JSON Schema parameters

#### Scenario: Invalid tool arguments
- **WHEN** the model calls a registered tool with invalid arguments
- **THEN** the registry SHALL reject execution, return a validation observation, and include retry guidance without crashing the request

#### Scenario: Duplicate tool registration
- **WHEN** two tools register with the same name
- **THEN** the registry SHALL preserve the first registered tool and reject the duplicate from runtime execution

### Requirement: Default Document Tools
The system SHALL provide a safe default non-wiki tool set for document reasoning.

#### Scenario: Default tools are available
- **WHEN** the runtime starts with default tool configuration
- **THEN** it SHALL expose `thinking`, `todo_write`, `knowledge_search`, `grep_chunks`, `list_knowledge_chunks`, `get_document_info`, `query_knowledge_graph`, and `read_skill` when their providers are configured

#### Scenario: Graph tool disabled
- **WHEN** graph retrieval is not configured
- **THEN** `query_knowledge_graph` SHALL be omitted or return a clear disabled observation without failing the whole runtime

#### Scenario: Wiki tools excluded
- **WHEN** the runtime builds its default tools
- **THEN** it SHALL NOT expose wiki read, write, search, rename, delete, issue, or source-document tools

### Requirement: Mandatory Deep Read Guard
The system SHALL enforce deep reading before factual final answers when search tools return candidate document or chunk identifiers.

#### Scenario: Search requires deep read
- **WHEN** `knowledge_search` or `grep_chunks` returns one or more candidate document or chunk identifiers
- **THEN** the runtime SHALL require `list_knowledge_chunks` or `get_document_info` to read full evidence before accepting a factual final answer

#### Scenario: Deep read skipped
- **WHEN** the model attempts to produce a factual answer after search results without deep-read evidence
- **THEN** the runtime SHALL continue the loop with a corrective observation instead of accepting the final answer

#### Scenario: No evidence found
- **WHEN** search tools return no usable candidates
- **THEN** the runtime SHALL allow a final answer that clearly states the answer cannot be determined from the available knowledge-base evidence

### Requirement: Runtime Limits
The system SHALL bound runtime cost and prevent stuck loops.

#### Scenario: Iteration limit reached
- **WHEN** the runtime reaches `AGENT_RUNTIME_MAX_ITERATIONS`
- **THEN** it SHALL stop requesting more tools and produce a final insufficient-evidence or partial-answer response from verified observations

#### Scenario: Tool output is large
- **WHEN** a tool returns output larger than the configured maximum
- **THEN** the registry SHALL truncate the output before appending it to model context while retaining a clear truncation marker

#### Scenario: Repeated empty model response
- **WHEN** the model repeatedly returns empty content and no tool calls
- **THEN** the runtime SHALL stop after the configured retry threshold and return a recoverable runtime error or fallback response
