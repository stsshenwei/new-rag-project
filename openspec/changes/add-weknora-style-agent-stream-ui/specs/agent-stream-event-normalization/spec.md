## ADDED Requirements

### Requirement: Normalized agent stream model
The frontend SHALL normalize chat SSE agent events into a stable `AgentStreamEvent` model.

#### Scenario: Agent trace event is normalized
- **WHEN** `/chat/stream` emits an `agent_trace` payload
- **THEN** the frontend SHALL append a normalized event containing event type, stage, status, safe summary, source chunk ids, timestamp, and raw metadata.

#### Scenario: Tool call event is normalized
- **WHEN** `/chat/stream` emits a `tool_call` payload
- **THEN** the frontend SHALL append a normalized tool-call event containing tool name, action, input summary, limits, required flag, timestamp, and raw metadata.

#### Scenario: Tool observation event is normalized
- **WHEN** `/chat/stream` emits a `tool_observation` payload
- **THEN** the frontend SHALL append a normalized tool-result event containing tool name, action, status, output summary, evidence counts, source chunk ids, timestamp, and raw metadata.

#### Scenario: Evidence summary event is normalized
- **WHEN** `/chat/stream` emits an `evidence_summary` payload
- **THEN** the frontend SHALL append a normalized evidence event containing tool counts, evidence item count, citation count, chunk count, graph path count, sufficiency status, confidence, and raw metadata.

#### Scenario: Citation verification event is normalized
- **WHEN** `/chat/stream` emits a `citation_verification` payload
- **THEN** the frontend SHALL append a normalized citation-check event containing valid status, summary, verified chunk ids, invalid chunk ids, and raw metadata.

### Requirement: Derived timeline steps
The frontend SHALL derive display timeline steps from normalized agent stream events.

#### Scenario: Trace event becomes stage step
- **WHEN** a normalized trace event represents an Agent FSM stage
- **THEN** the frontend SHALL derive a timeline step with a user-facing title, status, summary, and stage metadata.

#### Scenario: Tool call and result are paired
- **WHEN** a normalized tool-call event is followed by a matching tool-result event
- **THEN** the frontend SHALL render them as a single timeline step with final status and result summary.

#### Scenario: Tool call is still running
- **WHEN** a normalized tool-call event has no matching tool-result event yet
- **THEN** the frontend SHALL render the timeline step as running.

#### Scenario: Evidence and citation events become summary steps
- **WHEN** normalized evidence or citation-check events are present
- **THEN** the frontend SHALL derive compact timeline steps for evidence fusion and citation verification.

### Requirement: Agent run summary
The frontend SHALL derive an `AgentRunSummary` for each assistant message with agent events.

#### Scenario: Running summary
- **WHEN** an assistant message has active agent events and no final answer completion
- **THEN** the summary SHALL report running status, completed step count, total known step count, and elapsed time.

#### Scenario: Completed summary
- **WHEN** an assistant message has final answer completion and no failed required event
- **THEN** the summary SHALL report completed status, completed step count, total step count, elapsed time, evidence count, and citation status.

#### Scenario: Partial or failed summary
- **WHEN** one or more required tool or citation events fail
- **THEN** the summary SHALL report partial or failed status and include the failure summary.

### Requirement: Backward compatibility
The normalized event stream SHALL preserve existing chat behavior.

#### Scenario: Legacy raw RAG stream
- **WHEN** `/chat/stream` emits only `sources`, `reasoning`, and `token` payloads
- **THEN** the frontend SHALL continue rendering the answer, sources, and reasoning without requiring agent timeline events.

#### Scenario: Unknown event payload
- **WHEN** `/chat/stream` emits an unknown payload shape
- **THEN** the frontend SHALL ignore the unknown event for timeline purposes without breaking token streaming.

#### Scenario: Existing fields remain available
- **WHEN** normalized agent stream events are appended
- **THEN** existing message fields for content, sources, reasoning, feedback, and memory updates SHALL remain available.

### Requirement: Private reasoning safety
The frontend SHALL NOT display hidden chain-of-thought or private scratchpad fields.

#### Scenario: Private fields are scrubbed
- **WHEN** a normalized event contains keys such as `chain_of_thought`, `scratchpad`, `private_reasoning`, `raw_prompt`, or `memory_context`
- **THEN** the frontend SHALL exclude those fields from visible timeline text and detail metadata.

#### Scenario: Public trace is labelled as audit summary
- **WHEN** the timeline displays agent progress
- **THEN** the UI SHALL label it as an auditable execution summary rather than hidden model reasoning.
