## ADDED Requirements

### Requirement: Agent Round Trace
The system SHALL record and stream user-safe trace events for each ReAct runtime round.

#### Scenario: Round starts
- **WHEN** a ReAct round begins
- **THEN** the backend SHALL record a trace event with round number, elapsed timing metadata, and user-safe status summary

#### Scenario: Round completes
- **WHEN** a ReAct round completes
- **THEN** the backend SHALL record the number of tool calls, observation count, status, and duration for that round

#### Scenario: Final answer returned
- **WHEN** the runtime returns a final answer
- **THEN** the backend SHALL record a final trace event with final status, total rounds, total tool calls, and answer confidence or sufficiency status when available

### Requirement: Tool Call Trace
The system SHALL trace tool calls and observations from the runtime.

#### Scenario: Tool call starts
- **WHEN** the model requests a tool call
- **THEN** the backend SHALL emit a `tool_call` event with call id, tool name, bounded input summary, round number, and status

#### Scenario: Tool call returns
- **WHEN** a tool returns an observation
- **THEN** the backend SHALL emit a `tool_observation` event with call id, status, bounded output summary, source chunk ids when available, and error details when applicable

#### Scenario: Tool call fails
- **WHEN** a tool raises an error or returns failure
- **THEN** the backend SHALL mark the tool observation failed and preserve enough sanitized error detail for log-based troubleshooting

### Requirement: Trace Sanitization
The system SHALL sanitize all user-visible runtime trace payloads.

#### Scenario: Private fields present
- **WHEN** trace metadata contains `chain_of_thought`, `scratchpad`, `private_reasoning`, `raw_prompt`, `memory_context`, provider secrets, or raw tool payloads
- **THEN** the frontend-facing trace payload SHALL remove those fields before streaming or persistence

#### Scenario: Internal ids in visible summaries
- **WHEN** a trace summary is visible to users
- **THEN** it SHALL prefer document names and user-friendly labels and SHALL NOT expose internal implementation details unless required for debugging endpoints

### Requirement: Trace Compatibility
The system SHALL keep existing chat stream clients compatible while adding runtime trace events.

#### Scenario: Existing client ignores trace
- **WHEN** a client ignores `agent_trace`, `tool_call`, and `tool_observation` events
- **THEN** it SHALL still render the answer from existing `token` and `[DONE]` events

#### Scenario: Frontend timeline receives runtime events
- **WHEN** the frontend receives runtime trace events
- **THEN** it SHALL normalize them into the existing agent timeline model or a backwards-compatible extension

### Requirement: Backend Observability Integration
The system SHALL integrate runtime trace with backend logging and span storage.

#### Scenario: Request logging enabled
- **WHEN** request logging is enabled
- **THEN** runtime round and tool logs SHALL include the request trace id so operators can correlate chat requests with runtime tool activity

#### Scenario: Span persistence enabled
- **WHEN** backend span persistence is configured
- **THEN** the runtime SHALL persist spans for agent execution, each round, and each tool call with status, timestamps, duration, and sanitized error fields
