## ADDED Requirements

### Requirement: Domain Events Map To Compatible SSE Payloads
The system SHALL map Agent domain events to existing `/chat/stream` SSE payloads for backwards compatibility.

#### Scenario: Existing token client
- **WHEN** a client ignores unknown Agent event payloads and only reads `token` plus `[DONE]`
- **THEN** the client SHALL still render the final answer successfully

#### Scenario: Existing sources client
- **WHEN** a sourced reasoning response emits `agent_references`
- **THEN** `/chat/stream` SHALL also emit a compatible `sources` payload before answer tokens

### Requirement: Additive Agent Event SSE Payloads
The system SHALL expose new Agent lifecycle events additively in the chat stream.

#### Scenario: Agent query event
- **WHEN** reasoning mode receives a user question
- **THEN** `/chat/stream` SHALL emit an additive Agent event payload representing the query without removing the existing `conversation_id` event

#### Scenario: Thought and reflection events
- **WHEN** the runtime emits public thought or reflection domain events
- **THEN** `/chat/stream` SHALL expose additive payloads that the frontend can normalize while preserving compatible `agent_trace` behavior when needed

### Requirement: Answer Ordering Compatibility
The system SHALL preserve old stream semantics while enforcing references-before-answer ordering for reasoning mode.

#### Scenario: Sourced reasoning answer
- **WHEN** reasoning mode produces a sourced answer
- **THEN** `sources` and `agent_references` SHALL be emitted before the first `token` payload

#### Scenario: Final payload
- **WHEN** answer token streaming completes
- **THEN** the backend SHALL emit compatible final metadata or completion events without duplicating answer text in a way that old clients append twice

### Requirement: Completion Compatibility
The system SHALL complete all chat streams predictably.

#### Scenario: Normal completion
- **WHEN** an Agent run completes normally
- **THEN** `/chat/stream` SHALL emit `agent_complete` or equivalent additive completion metadata and then emit `data: [DONE]`

#### Scenario: Error completion
- **WHEN** an Agent run fails fatally
- **THEN** `/chat/stream` SHALL emit a compatible `error` payload and still finish with `data: [DONE]`

### Requirement: Legacy Event Name Consistency
The system SHALL keep frontend and backend event naming consistent.

#### Scenario: Tool result normalization
- **WHEN** the backend emits a tool result or observation
- **THEN** frontend stream types and normalizers SHALL agree on the accepted event name and SHALL handle existing `tool_observation` payloads
