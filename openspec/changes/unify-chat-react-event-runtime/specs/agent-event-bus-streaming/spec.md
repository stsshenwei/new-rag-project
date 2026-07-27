## ADDED Requirements

### Requirement: Runtime Event Publication
The runtime SHALL publish domain events through a request-scoped event bus or equivalent event stream boundary.

#### Scenario: Event emitted by runtime phase
- **WHEN** a runtime phase starts, completes, fails, or produces streamable content
- **THEN** the runtime SHALL publish a sanitized domain event instead of directly coupling phase logic to SSE serialization

#### Scenario: Event includes common fields
- **WHEN** the event bus receives a domain event
- **THEN** the event SHALL include stable type, run id, sequence, status, timestamp, and bounded payload fields

### Requirement: SSE Stream Handler Subscription
The SSE stream handler SHALL subscribe to runtime events and translate them into `/chat/stream` payloads.

#### Scenario: Domain event received
- **WHEN** the SSE stream handler receives a runtime domain event
- **THEN** it SHALL emit an additive SSE payload for that event using the existing `data: <json>` framing

#### Scenario: Backward-compatible payload needed
- **WHEN** the domain event corresponds to sources, answer tokens, errors, or final metadata used by legacy clients
- **THEN** the SSE stream handler SHALL also emit the compatible legacy payload without duplicating answer text

### Requirement: Completion Event Guarantee
The event stream SHALL guarantee terminal completion semantics for started runs.

#### Scenario: Normal return
- **WHEN** runtime execution reaches a normal return path
- **THEN** the event stream SHALL include `agent_complete` before the transport-level `[DONE]`

#### Scenario: Exception path
- **WHEN** runtime execution raises an exception after the run starts
- **THEN** the event stream SHALL include `agent_error` and a terminal completion-compatible event before `[DONE]` when the connection remains writable

### Requirement: Streaming And Snapshot Event Semantics
The event stream SHALL distinguish streamable content events from snapshot lifecycle events.

#### Scenario: Final answer streaming
- **WHEN** the runtime streams final answer text
- **THEN** the stream SHALL provide incremental answer content while preserving a final answer lifecycle event

#### Scenario: Tool event snapshot
- **WHEN** a tool call or tool result occurs
- **THEN** the stream SHALL emit a bounded snapshot event rather than tokenizing the tool payload

### Requirement: Subscription Cleanup
The event bus SHALL release request-scoped subscribers and resources after stream termination.

#### Scenario: Client disconnect
- **WHEN** a client disconnects before the run finishes
- **THEN** the backend SHALL stop writing SSE payloads, clean up request-scoped subscriptions, and close runtime spans safely
