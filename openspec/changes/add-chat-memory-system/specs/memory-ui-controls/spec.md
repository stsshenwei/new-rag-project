## ADDED Requirements

### Requirement: Active conversation tracking
The frontend SHALL track the active conversation ID returned by the backend.

#### Scenario: Store streamed conversation ID
- **WHEN** the chat stream emits a `conversation_id`
- **THEN** the frontend SHALL store it and include it in subsequent chat requests for the same chat.

#### Scenario: New chat clears conversation
- **WHEN** the user activates the new-chat control
- **THEN** the frontend SHALL clear the local transcript and active conversation ID.

### Requirement: Memory update notice
The frontend SHALL display a non-blocking notice when the backend reports saved or updated memories.

#### Scenario: Show remembered item
- **WHEN** the chat stream emits a memory update event
- **THEN** the frontend SHALL show a concise notice identifying the memory that was saved or updated.

#### Scenario: Do not block answer rendering
- **WHEN** a memory update event arrives during or after answer streaming
- **THEN** the frontend SHALL continue rendering answer tokens and completion normally.

### Requirement: Memory management surface
The frontend SHALL provide a user-accessible surface to view and delete saved memories.

#### Scenario: List saved memories
- **WHEN** the user opens memory management
- **THEN** the frontend SHALL request active memories from the backend and render their content and type.

#### Scenario: Delete saved memory
- **WHEN** the user deletes a memory from memory management
- **THEN** the frontend SHALL call the backend deletion endpoint and remove the memory from the displayed active list after success.

### Requirement: Temporary chat control
The frontend SHALL provide a way to send chat requests without long-term memory.

#### Scenario: Disable memory for request
- **WHEN** the user enables temporary or memory-off mode for a chat request
- **THEN** the frontend SHALL send a request flag that prevents long-term memory recall and extraction for that request.
