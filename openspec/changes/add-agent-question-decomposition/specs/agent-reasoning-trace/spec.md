## ADDED Requirements

### Requirement: Visible agent plan event
The system SHALL emit a user-visible agent plan summary when decomposition is used.

#### Scenario: Emit agent plan
- **WHEN** a question is decomposed
- **THEN** `/chat/stream` SHALL emit an `agent_plan` SSE payload before final answer tokens.

#### Scenario: No hidden chain-of-thought
- **WHEN** the agent plan is emitted
- **THEN** the payload SHALL contain explicit planning fields and SHALL NOT contain hidden chain-of-thought text.

### Requirement: Agent step events
The system SHALL emit visible execution step summaries for subquestion retrieval.

#### Scenario: Emit subquestion start
- **WHEN** retrieval starts for a subquestion
- **THEN** `/chat/stream` SHALL emit an `agent_step` payload identifying the subquestion and status.

#### Scenario: Emit subquestion sources
- **WHEN** retrieval completes for a subquestion
- **THEN** `/chat/stream` SHALL emit a `subquestion_sources` payload with the subquestion ID and source summary.

### Requirement: Backwards-compatible stream
The system SHALL preserve existing stream behavior for clients that do not render agent events.

#### Scenario: Existing token stream still works
- **WHEN** a client ignores `agent_plan`, `agent_step`, and `subquestion_sources`
- **THEN** the client SHALL still receive final `sources`, `reasoning`, `token`, and `[DONE]` events.

#### Scenario: Simple question omits agent events
- **WHEN** decomposition is not used
- **THEN** the stream SHALL omit agent-specific events and use the existing chat stream shape.

### Requirement: Frontend reasoning panel
The frontend SHALL render agent plan and execution summaries in an expandable reasoning panel.

#### Scenario: Render plan and subquestions
- **WHEN** an `agent_plan` event is received
- **THEN** the frontend SHALL show the decomposition decision and subquestions in the reasoning panel.

#### Scenario: Render evidence path
- **WHEN** subquestion source events are received
- **THEN** the frontend SHALL show the source summary grouped by subquestion.

### Requirement: Fallback visibility
The system SHALL report decomposition fallback as an audit summary when planning fails after being attempted.

#### Scenario: Planner fallback reported
- **WHEN** decomposition is attempted but falls back to single-pass RAG
- **THEN** the reasoning trace SHALL include a fallback reason suitable for user-facing display.
