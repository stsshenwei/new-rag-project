## ADDED Requirements

### Requirement: Temporary Attachment Upload
The system SHALL allow users to upload files as temporary chat attachments for the current question only.

#### Scenario: Attachment upload succeeds
- **WHEN** the user uploads a supported file from the chat composer
- **THEN** the backend stores it as a temporary chat attachment and returns an attachment id that can be included in a chat request

#### Scenario: Attachment upload fails
- **WHEN** the user uploads an unsupported or invalid file
- **THEN** the system reports a clear validation error and does not attach the file to the pending message

### Requirement: Attachment-Bound Chat Request
The system SHALL allow `/chat/stream` requests to reference temporary attachment ids and include their parsed content in the current answer context.

#### Scenario: Message with attachment ids
- **WHEN** `/chat/stream` receives valid temporary attachment ids
- **THEN** the backend parses or loads their extracted content and makes it available to the selected quick or reasoning answer path for that request

#### Scenario: Attachment source labeling
- **WHEN** an answer uses temporary attachment content
- **THEN** any displayed source or trace metadata labels the evidence as a temporary attachment rather than a knowledge base document

#### Scenario: Missing attachment id
- **WHEN** `/chat/stream` receives an unknown or expired attachment id
- **THEN** the request reports a clear error and does not proceed with a misleading answer

### Requirement: No Knowledge Base Persistence
Temporary chat attachments MUST NOT be persisted as knowledge base documents, vector chunks, upload batch files, or permanent document traces.

#### Scenario: Attachment is used for one question
- **WHEN** a temporary attachment is used in a chat request
- **THEN** it is not visible in the knowledge base document list after the request completes

#### Scenario: Attachment is not indexed
- **WHEN** a temporary attachment is parsed
- **THEN** no permanent vector records or knowledge base chunk records are created for it

### Requirement: Temporary Attachment Cleanup
The system SHALL clean up temporary chat attachments after use or expiration.

#### Scenario: Request completes
- **WHEN** a chat request using temporary attachments completes successfully or fails
- **THEN** the system marks those attachments as consumed or eligible for cleanup

#### Scenario: Attachment expires
- **WHEN** a temporary attachment exceeds its configured retention window
- **THEN** the system removes or ignores the attachment so it cannot be reused indefinitely
