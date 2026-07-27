## ADDED Requirements

### Requirement: Agent Domain Event Taxonomy
The system SHALL define first-class Agent domain events for reasoning-mode execution.

#### Scenario: Runtime emits domain lifecycle
- **WHEN** a reasoning-mode Agent run starts and completes normally
- **THEN** the backend SHALL emit domain events representing query, public thought, tool call, tool result, reflection, references, final answer, and completion in a stable lifecycle order

#### Scenario: Event names are stable
- **WHEN** backend code serializes Agent domain events
- **THEN** event names SHALL use stable machine-readable identifiers and SHALL NOT depend on frontend labels or localized display text

### Requirement: Domain Event Payload Shape
The system SHALL serialize every Agent domain event with a bounded, typed payload.

#### Scenario: Common event fields
- **WHEN** any Agent domain event is serialized
- **THEN** it SHALL include event id, event type, run id, sequence number, status, timestamp, and sanitized payload data

#### Scenario: Event payloads are bounded
- **WHEN** an Agent domain event contains summaries, tool inputs, tool outputs, or metadata
- **THEN** the backend SHALL truncate or summarize unbounded fields before exposing them to the frontend

### Requirement: Public Thought And Reflection Safety
The system SHALL expose public thought and reflection events only as user-safe audit summaries.

#### Scenario: Hidden reasoning is present internally
- **WHEN** internal model output or tool metadata contains chain-of-thought, scratchpad, private reasoning, raw prompt text, memory context, provider payloads, or secrets
- **THEN** Agent domain events SHALL remove those fields before streaming or persistence

#### Scenario: Public reflection fields
- **WHEN** the backend emits an `agent_reflection` event
- **THEN** the payload SHALL describe public validity, evidence gap, correction query, completion status, and source chunk ids when available without exposing hidden chain-of-thought

### Requirement: References Before Final Answer
The system SHALL emit reference events before final answer events for sourced reasoning responses.

#### Scenario: Sourced answer
- **WHEN** reasoning mode has traceable knowledge-base citations for an answer
- **THEN** `agent_references` SHALL be emitted before the first `agent_final_answer` content event

#### Scenario: No sufficient references
- **WHEN** reasoning mode cannot find sufficient traceable evidence
- **THEN** the backend SHALL emit a completion-safe insufficient-evidence event sequence and SHALL NOT fabricate references

### Requirement: Agent Error Event
The system SHALL represent recoverable and fatal Agent failures as domain events.

#### Scenario: Recoverable tool failure
- **WHEN** a tool call fails but the Agent can continue
- **THEN** the backend SHALL emit an `agent_tool_result` event with failed status and sanitized error summary

#### Scenario: Fatal runtime failure
- **WHEN** the Agent runtime cannot continue
- **THEN** the backend SHALL emit an `agent_error` event followed by a completion event compatible with `/chat/stream`
