## ADDED Requirements

### Requirement: Configurable agentic chat workflow
The system SHALL allow `/chat/stream` to use the finite-state Agentic Retrieval workflow when chat agent mode is enabled.

#### Scenario: Agentic chat mode disabled
- **WHEN** `CHAT_AGENTIC_WORKFLOW_ENABLED` is false
- **THEN** `/chat/stream` SHALL preserve the existing Raw RAG streaming path.

#### Scenario: Agentic chat mode enabled
- **WHEN** `CHAT_AGENTIC_WORKFLOW_ENABLED` is true and `AgenticRetrievalWorkflow` is available
- **THEN** `/chat/stream` SHALL execute the Agentic Retrieval workflow instead of directly calling `hybrid_retrieve_hits()` and `stream_answer()` from the route handler.

#### Scenario: Workflow unavailable
- **WHEN** `CHAT_AGENTIC_WORKFLOW_ENABLED` is true but the workflow cannot be constructed
- **THEN** `/chat/stream` SHALL fail open to the existing Raw RAG streaming path and record the fallback in debug or trace metadata.

### Requirement: Streaming workflow execution
The system SHALL expose a streaming workflow API that yields events as finite-state execution progresses.

#### Scenario: Stream states as they execute
- **WHEN** agentic chat mode handles a message
- **THEN** the workflow SHALL emit visible events for question analysis, retrieval planning, permission scope check, retrieval execution, evidence fusion, sufficiency check, context building, answer generation, citation verification, and return.

#### Scenario: Tool calls remain planned and bounded
- **WHEN** the streaming workflow runs retrieval
- **THEN** it SHALL call only tools planned by `RetrievalPlanner` and approved by the existing tool whitelist.

#### Scenario: No free-form agent loop
- **WHEN** agentic chat mode is enabled
- **THEN** the system SHALL NOT allow an LLM to select arbitrary tools or run an unbounded tool loop.

### Requirement: Chat answer generation remains token-streamed
The system SHALL preserve token streaming for final chat answers in agentic chat mode.

#### Scenario: Sufficient evidence
- **WHEN** fused and verified evidence is sufficient
- **THEN** `/chat/stream` SHALL stream answer tokens generated from the agent-built context.

#### Scenario: Insufficient evidence
- **WHEN** required evidence is missing or insufficient
- **THEN** `/chat/stream` SHALL stream an explicit insufficient-evidence answer instead of an unsupported factual answer.

#### Scenario: Citation verification failure
- **WHEN** citation verification fails for the candidate answer or graph evidence
- **THEN** `/chat/stream` SHALL not complete with an unsupported factual answer and SHALL emit a citation verification failure event.

### Requirement: Chat memory compatibility
The system SHALL preserve conversation and memory behavior when agentic chat mode is enabled.

#### Scenario: Conversation id emitted first
- **WHEN** `/chat/stream` receives a request in agentic chat mode
- **THEN** it SHALL emit `conversation_id` before retrieval or answer events.

#### Scenario: Conversation context is used for generation
- **WHEN** the request belongs to an existing conversation
- **THEN** the agentic answer generation SHALL receive the same conversation context used by the current Raw RAG chat path.

#### Scenario: Long-term memory remains prompt context
- **WHEN** memory is enabled for a chat request
- **THEN** memory context SHALL be passed to answer generation but SHALL NOT be treated as citable document or graph evidence.

#### Scenario: Memory update after answer
- **WHEN** the streamed answer completes
- **THEN** the backend SHALL persist the assistant message, summarize as needed, process memory updates, and emit `memory_updated` when updates exist.
