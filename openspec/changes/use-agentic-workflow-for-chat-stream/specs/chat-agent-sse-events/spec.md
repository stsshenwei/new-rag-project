## ADDED Requirements

### Requirement: Backwards-compatible SSE payloads
The system SHALL preserve existing `/chat/stream` SSE event compatibility in agentic chat mode.

#### Scenario: Existing events remain available
- **WHEN** `/chat/stream` runs in agentic chat mode
- **THEN** it SHALL still emit compatible `conversation_id`, `sources`, `reasoning`, `token`, optional `memory_updated`, and `[DONE]` events.

#### Scenario: Existing token clients continue to work
- **WHEN** a client ignores unknown agent event fields and only reads `token`
- **THEN** the client SHALL still be able to render the final answer.

#### Scenario: Sources before tokens
- **WHEN** agentic chat mode emits a sourced answer
- **THEN** `sources` SHALL be emitted before the first `token` event.

### Requirement: Visible agent process events
The system SHALL stream visible agent process events before final answer tokens.

#### Scenario: Agent trace event
- **WHEN** the streaming workflow enters or completes a state
- **THEN** `/chat/stream` SHALL emit an `agent_trace` payload with stage, status, summary, and relevant source chunk ids or metadata.

#### Scenario: Tool call event
- **WHEN** a planned retrieval tool starts
- **THEN** `/chat/stream` SHALL emit a `tool_call` payload with tool name, action, bounded input summary, and limits.

#### Scenario: Tool observation event
- **WHEN** a planned retrieval tool completes, skips, or fails
- **THEN** `/chat/stream` SHALL emit a `tool_observation` payload with status, observation summary, evidence counts, and source chunk ids when available.

#### Scenario: Evidence summary event
- **WHEN** evidence fusion and sufficiency checking completes
- **THEN** `/chat/stream` SHALL emit an `evidence_summary` payload with tool counts, evidence counts, used chunks, used entities, graph paths, confidence, and sufficiency status.

#### Scenario: Citation verification event
- **WHEN** citation verification completes
- **THEN** `/chat/stream` SHALL emit a `citation_verification` payload with verification status and a user-facing summary.

### Requirement: Trace safety
The system SHALL expose audit summaries without hidden reasoning.

#### Scenario: No hidden chain-of-thought
- **WHEN** `/chat/stream` emits agent process events
- **THEN** those events SHALL NOT include hidden chain-of-thought, private scratchpad text, or raw model deliberation.

#### Scenario: Tool inputs are bounded
- **WHEN** `/chat/stream` emits tool call metadata
- **THEN** the payload SHALL summarize inputs and limits without dumping unbounded prompt text or sensitive memory context.

### Requirement: Error and fallback stream compatibility
The system SHALL finish streams predictably when agentic chat execution fails.

#### Scenario: Agent event failure
- **WHEN** a planned tool fails but the workflow can continue
- **THEN** `/chat/stream` SHALL emit a failed `tool_observation` and continue according to evidence sufficiency rules.

#### Scenario: Fatal workflow failure
- **WHEN** the agentic streaming workflow raises an unrecoverable error
- **THEN** `/chat/stream` SHALL emit an `error` payload and `[DONE]` using the existing error stream convention.

#### Scenario: Raw RAG fallback
- **WHEN** agentic chat mode falls back to Raw RAG
- **THEN** the stream SHALL remain compatible with the existing Raw RAG SSE shape.
