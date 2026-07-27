## ADDED Requirements

### Requirement: Shared Chat Runtime Execution Model
The system SHALL execute quick and reasoning chat modes through a shared runtime model with explicit Execute, loop, iteration, and terminal lifecycle stages.

#### Scenario: Quick mode enters shared runtime
- **WHEN** `/chat/stream` receives a quick-mode request while unified runtime is enabled
- **THEN** the backend SHALL route the request through the shared runtime execution model instead of the legacy raw stream path

#### Scenario: Reasoning mode enters shared runtime
- **WHEN** `/chat/stream` receives a reasoning-mode request while Agent runtime is available
- **THEN** the backend SHALL route the request through the same shared runtime execution model with reasoning policy settings

### Requirement: ReAct Iteration Phases
The runtime SHALL model each loop iteration as Think, Analyze, Act, and Observe phases.

#### Scenario: Model requests tools
- **WHEN** the Think phase receives an LLM response containing tool calls
- **THEN** Analyze SHALL mark the iteration as not done, Act SHALL execute allowed tools, and Observe SHALL append sanitized tool observations before the next iteration

#### Scenario: Model stops without tools
- **WHEN** the Think phase receives an LLM response with no tool calls and a permitted final answer
- **THEN** Analyze SHALL mark the run as done and the runtime SHALL proceed to references, final answer, and completion events

### Requirement: Loop Guardrails
The runtime SHALL enforce policy-defined iteration, retry, and repeated-response limits for every chat mode.

#### Scenario: Iteration limit reached
- **WHEN** a run reaches its policy-defined maximum iteration count without a valid final answer
- **THEN** the runtime SHALL stop the loop and produce a bounded insufficient-or-partial answer instead of continuing indefinitely

#### Scenario: Empty response retries exhausted
- **WHEN** the model repeatedly returns no final answer and no tool calls beyond the configured retry limit
- **THEN** the runtime SHALL stop with a sanitized failure or insufficient-evidence outcome

### Requirement: Unified Terminal Lifecycle
The runtime SHALL produce a terminal lifecycle outcome for every run that starts.

#### Scenario: Normal completion
- **WHEN** a run produces a final answer
- **THEN** the runtime SHALL emit a final answer event followed by a completion event with run status and summary metadata

#### Scenario: Runtime failure
- **WHEN** an unhandled runtime error prevents further execution
- **THEN** the runtime SHALL emit an error event and a terminal completion-compatible outcome when the SSE stream is still writable
