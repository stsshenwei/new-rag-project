## ADDED Requirements

### Requirement: Per-Message Chat Mode
The system SHALL allow each chat message request to choose an answer mode using a `chat_mode` value of `quick` or `reasoning`.

#### Scenario: Quick mode request
- **WHEN** `/chat/stream` receives `chat_mode` set to `quick`
- **THEN** the backend routes the request through the direct retrieval-answer path regardless of the global agentic chat setting

#### Scenario: Reasoning mode request
- **WHEN** `/chat/stream` receives `chat_mode` set to `reasoning`
- **THEN** the backend routes the request through the agentic reasoning chat path and streams safe reasoning or timeline events when available

#### Scenario: Legacy request without mode
- **WHEN** `/chat/stream` receives a request without `chat_mode`
- **THEN** the backend preserves the current legacy behavior controlled by existing backend configuration

### Requirement: Chat Mode Message Metadata
The system SHALL record the selected chat mode with each user/assistant exchange so the UI can display or reason about how a response was generated.

#### Scenario: User sends quick mode
- **WHEN** a user sends a message with `chat_mode` set to `quick`
- **THEN** the stored conversation metadata and frontend message state include `quick` for that exchange

#### Scenario: User sends reasoning mode
- **WHEN** a user sends a message with `chat_mode` set to `reasoning`
- **THEN** the stored conversation metadata and frontend message state include `reasoning` for that exchange

### Requirement: Reasoning Availability Handling
The system SHALL handle unavailable reasoning mode explicitly.

#### Scenario: Reasoning workflow unavailable
- **WHEN** `/chat/stream` receives `chat_mode` set to `reasoning` but the agentic workflow is unavailable
- **THEN** the response reports a clear error and MUST NOT silently fall back to quick mode

#### Scenario: Quick mode remains available
- **WHEN** reasoning mode is unavailable
- **THEN** users can still submit messages with `chat_mode` set to `quick`

### Requirement: Safe Reasoning Display
The system SHALL show only safe trace summaries for reasoning mode and MUST NOT expose hidden chain-of-thought.

#### Scenario: Reasoning events are streamed
- **WHEN** the backend emits reasoning or agent timeline events
- **THEN** the frontend renders safe status, tool, retrieval, citation, and summary information without exposing hidden chain-of-thought
