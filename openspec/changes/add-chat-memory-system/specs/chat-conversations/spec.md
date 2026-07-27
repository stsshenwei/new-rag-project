## ADDED Requirements

### Requirement: Conversation sessions
The system SHALL support stable conversation sessions for chat requests.

#### Scenario: Create conversation when absent
- **WHEN** a client posts to `/chat/stream` with a valid `message` and no `conversation_id`
- **THEN** the backend SHALL create a new conversation and emit the generated `conversation_id` in the stream.

#### Scenario: Continue existing conversation
- **WHEN** a client posts to `/chat/stream` with a valid existing `conversation_id`
- **THEN** the backend SHALL append the new user and assistant messages to that conversation.

#### Scenario: Preserve legacy request compatibility
- **WHEN** a client posts to `/chat/stream` with only `{ "message": "..." }`
- **THEN** the backend SHALL continue streaming sources, reasoning, answer tokens, and completion using the existing SSE event format.

### Requirement: Recent conversation context
The system SHALL include a bounded window of recent conversation messages when answering within a conversation.

#### Scenario: Follow-up question uses recent context
- **WHEN** a user asks a follow-up question that depends on prior turns in the same conversation
- **THEN** the backend SHALL include relevant recent conversation turns in the LLM prompt before generating the answer.

#### Scenario: Context window remains bounded
- **WHEN** a conversation contains more messages than the configured recent-turn limit
- **THEN** the backend SHALL include only the bounded recent window plus any available summary instead of the full transcript.

### Requirement: Rolling conversation summaries
The system SHALL maintain a rolling summary for long conversations.

#### Scenario: Summarize old messages
- **WHEN** a conversation exceeds the configured message or token threshold
- **THEN** the backend SHALL summarize older messages and store the summary on the conversation record.

#### Scenario: Use summary in prompt
- **WHEN** a conversation has a stored summary
- **THEN** the backend SHALL include that summary in the prompt along with the recent message window.

### Requirement: Conversation persistence
The system SHALL persist conversation records and chat messages outside frontend-only state.

#### Scenario: Conversation survives page refresh
- **WHEN** the frontend reloads while retaining an active `conversation_id`
- **THEN** subsequent messages using that ID SHALL continue the same backend conversation.

#### Scenario: New chat starts clean short-term context
- **WHEN** the user starts a new chat
- **THEN** the frontend SHALL clear the active conversation ID and local transcript without deleting long-term memories.
