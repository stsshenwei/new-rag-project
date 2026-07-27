## ADDED Requirements

### Requirement: Durable memory storage
The system SHALL store long-term memories separately from uploaded documents, feedback documents, and vector index ingest state.

#### Scenario: Memory survives document reindex
- **WHEN** the document corpus is ingested or reindexed
- **THEN** active long-term memories SHALL remain available and SHALL NOT be deleted by document ingest.

#### Scenario: Memory is not listed as a document
- **WHEN** a client requests the dataset document list
- **THEN** long-term memories SHALL NOT appear as uploaded, feedback, or source documents.

### Requirement: Memory extraction
The system SHALL evaluate completed chat exchanges for durable memory candidates when memory is enabled.

#### Scenario: Save stable preference
- **WHEN** a user clearly states a durable preference
- **THEN** the system SHALL save or update an active memory representing that preference.

#### Scenario: Ignore one-off task
- **WHEN** a user asks for a transient action or single-turn task
- **THEN** the system SHALL NOT save it as long-term memory.

#### Scenario: Avoid sensitive memory
- **WHEN** a chat exchange contains credentials, secrets, or highly sensitive personal data
- **THEN** the system SHALL NOT save that content as long-term memory.

### Requirement: Memory deduplication and updates
The system SHALL deduplicate and update related memories instead of accumulating conflicting duplicates.

#### Scenario: Merge same preference
- **WHEN** a new memory candidate has the same normalized key as an existing active memory
- **THEN** the system SHALL update the existing memory rather than creating a duplicate active memory.

#### Scenario: Supersede changed preference
- **WHEN** a user explicitly changes a remembered preference
- **THEN** the system SHALL make the new preference active and SHALL NOT continue injecting the superseded preference.

### Requirement: Memory recall
The system SHALL recall relevant active long-term memories for chat prompt assembly.

#### Scenario: Inject relevant memory
- **WHEN** a chat request is processed with memory enabled
- **THEN** the backend SHALL include relevant active memories in the LLM prompt with clear labels that distinguish memory from document evidence.

#### Scenario: Respect disabled memory
- **WHEN** a chat request disables memory or uses temporary mode
- **THEN** the backend SHALL NOT inject long-term memories and SHALL NOT create new long-term memories from that request.

### Requirement: Memory deletion
The system SHALL allow users to delete saved long-term memories.

#### Scenario: Delete memory
- **WHEN** a user deletes a memory
- **THEN** the backend SHALL mark that memory inactive or deleted and SHALL exclude it from future prompt assembly.

#### Scenario: Forget request
- **WHEN** a user explicitly asks the assistant to forget a saved memory
- **THEN** the system SHALL delete or archive the matching memory when it can identify the target.
