## ADDED Requirements

### Requirement: Empty Chat Home
The system SHALL present an empty chat home when a conversation has no messages, including a prominent Bee title, a `你可以这样问我` prompt area, suggested question chips, and the chat composer.

#### Scenario: New conversation home
- **WHEN** the user opens a new chat with no messages
- **THEN** the page displays the Bee title, suggested question chips, and composer without requiring any previous conversation context

#### Scenario: Suggested question starts input
- **WHEN** the user selects a suggested question chip
- **THEN** the selected question is placed into the composer or submitted according to the implemented interaction without losing selected mode or knowledge base scope

#### Scenario: Home hides after conversation starts
- **WHEN** the conversation contains at least one user or assistant message
- **THEN** the welcome title and suggested question chips are hidden and the normal message thread is shown

### Requirement: Focused Composer Toolbar
The system SHALL provide a focused composer toolbar containing answer mode selection, temporary file upload, knowledge base scope selection, and send controls, and MUST NOT show a model selector.

#### Scenario: Composer controls are available
- **WHEN** the chat composer is displayed
- **THEN** it provides controls for `快速问答`, `智能推理`, temporary file upload, knowledge base selection, and sending the message

#### Scenario: Model selector is hidden
- **WHEN** the chat composer is displayed
- **THEN** no visible model selector is rendered

#### Scenario: Send remains guarded
- **WHEN** the composer input is empty or a chat request is already streaming
- **THEN** the send control is disabled or guarded so duplicate empty requests are not submitted

### Requirement: Composer Knowledge Base Scope
The system SHALL allow users to choose the retrieval knowledge base scope from inside the composer.

#### Scenario: Default knowledge base scope
- **WHEN** the user has not selected any explicit knowledge base
- **THEN** the composer displays the default knowledge base scope

#### Scenario: Multiple knowledge bases selected
- **WHEN** the user selects one or more knowledge bases
- **THEN** the composer displays a compact scope label and future chat requests include the selected knowledge base ids

#### Scenario: Scope persists locally
- **WHEN** the user changes the selected knowledge base scope
- **THEN** the selection is preserved across page refreshes using the existing local persistence behavior
