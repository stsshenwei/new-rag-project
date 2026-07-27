## ADDED Requirements

### Requirement: Visible agent trace
The system SHALL expose a workbuddy-style visible process trace for agentic retrieval.

#### Scenario: Trace summarizes each state
- **WHEN** the workflow executes a state
- **THEN** it SHALL append a trace step with stage, status, user-facing summary, and relevant evidence or tool metadata.

#### Scenario: Trace excludes hidden chain-of-thought
- **WHEN** trace steps are returned or streamed
- **THEN** they SHALL NOT include hidden chain-of-thought, private model deliberation, or raw scratchpad text.

### Requirement: Tool call and observation trace
The system SHALL record approved tool calls and observations.

#### Scenario: Tool call trace
- **WHEN** a retrieval tool is called
- **THEN** the trace SHALL include the tool name, bounded input summary, status, and relevant limits.

#### Scenario: Tool observation trace
- **WHEN** a retrieval tool returns
- **THEN** the trace SHALL include an observation summary, evidence counts, source chunk ids when available, and failure reason when applicable.

### Requirement: Streaming trace compatibility
The system SHALL optionally stream agent trace events without breaking existing chat stream clients.

#### Scenario: Optional trace events are emitted before tokens
- **WHEN** `/chat/stream` uses agentic retrieval with trace streaming enabled
- **THEN** it SHALL emit optional trace payloads before final answer token events.

#### Scenario: Existing stream events remain
- **WHEN** `/chat/stream` uses or does not use agentic retrieval
- **THEN** existing `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` events SHALL remain compatible.

#### Scenario: Simple clients can ignore trace events
- **WHEN** a client ignores agent trace payloads
- **THEN** it SHALL still be able to render the final answer from existing token events.
