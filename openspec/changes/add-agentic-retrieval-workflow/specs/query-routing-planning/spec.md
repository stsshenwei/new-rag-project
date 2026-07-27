## ADDED Requirements

### Requirement: Query routing
The system SHALL classify each agentic query into one supported question type before planning retrieval.

#### Scenario: Route supported question types
- **WHEN** a user asks a question
- **THEN** QueryRouter SHALL classify it as one of `fact`, `source`, `howto`, `troubleshooting`, `comparison`, `impact`, `dependency`, `summary`, or `decision`.

#### Scenario: Unknown question falls back safely
- **WHEN** QueryRouter cannot confidently classify a question
- **THEN** it SHALL use a safe fallback route that plans Raw RAG retrieval and records the fallback in trace metadata.

### Requirement: Retrieval planning by question type
The system SHALL map each question type to deterministic retrieval tool choices.

#### Scenario: Fact plan uses Raw RAG and entity search
- **WHEN** QueryRouter returns `fact`
- **THEN** RetrievalPlanner SHALL include Raw RAG and GraphRetriever entity search.

#### Scenario: Source plan uses Raw RAG only
- **WHEN** QueryRouter returns `source`
- **THEN** RetrievalPlanner SHALL include Raw RAG and SHALL NOT require graph retrieval.

#### Scenario: Impact plan requires graph retrieval
- **WHEN** QueryRouter returns `impact`
- **THEN** RetrievalPlanner SHALL include GraphRetriever neighbor or path retrieval and Raw evidence validation.

#### Scenario: Dependency plan requires graph path search
- **WHEN** QueryRouter returns `dependency`
- **THEN** RetrievalPlanner SHALL include GraphRetriever path search as a required tool.

#### Scenario: Troubleshooting plan combines graph raw and keyword tools
- **WHEN** QueryRouter returns `troubleshooting`
- **THEN** RetrievalPlanner SHALL include GraphRetriever for Error/Config/Service context, Raw RAG, and Keyword Search.

### Requirement: Plan constraints
The system SHALL produce bounded retrieval plans that use only approved tools.

#### Scenario: Approved tools only
- **WHEN** RetrievalPlanner creates a plan
- **THEN** every planned tool SHALL be one of `RawRAGTool`, `KeywordSearchTool`, or `GraphRetrieverTool`.

#### Scenario: Tool limits are enforced
- **WHEN** a retrieval plan is created
- **THEN** the plan SHALL include bounded limits for retrieval depth, top-k, and maximum tool calls.
