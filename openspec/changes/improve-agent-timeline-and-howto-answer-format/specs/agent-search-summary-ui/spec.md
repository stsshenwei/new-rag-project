## ADDED Requirements

### Requirement: Search summary banner
The chat UI SHALL render a compact retrieval status summary for assistant messages.

#### Scenario: Search is running
- **WHEN** an assistant message is streaming and retrieval has not completed
- **THEN** the UI SHALL show a compact status such as `检索中...`

#### Scenario: Search completes with citations
- **WHEN** an assistant message has source citations or verified citation data
- **THEN** the UI SHALL show `检索完成 · 引用了 N 篇文档` using a deduplicated document/source count

#### Scenario: No citable evidence
- **WHEN** the evidence summary indicates insufficient evidence or the message has no usable citations
- **THEN** the UI SHALL show a clear insufficient-evidence status instead of implying a successful sourced answer

#### Scenario: Citation verification fails
- **WHEN** citation verification reports invalid citations or invalid chunks
- **THEN** the UI SHALL show a citation-failed status and SHALL NOT present the answer as fully verified

### Requirement: Search summary compatibility
The search summary SHALL preserve existing chat answer, source, reasoning, memory, feedback, and document preview behavior.

#### Scenario: Existing sources remain clickable
- **WHEN** a message renders the search summary and source buttons
- **THEN** source buttons SHALL remain visible and clickable

#### Scenario: Non-agentic Raw RAG mode
- **WHEN** `/chat/stream` emits only legacy `sources`, `reasoning`, and `token` payloads
- **THEN** the UI SHALL still derive the search summary from sources and answer state

#### Scenario: Agentic mode
- **WHEN** `/chat/stream` emits agent events, evidence summary, and citation verification
- **THEN** the UI SHALL include those signals when deriving the search summary

#### Scenario: Quick answer mode
- **WHEN** `/chat/stream` emits only quick Raw RAG events
- **THEN** the UI SHALL show the summary and citations without rendering a fake intelligent-reasoning timeline
