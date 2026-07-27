## ADDED Requirements

### Requirement: Quick mode emits a public RAG execution trace

The system SHALL emit a bounded, public execution trace for `chat_mode=quick` that represents the quick RAG process without switching the request to reasoning mode or an open-ended agent runtime.

#### Scenario: Quick answer streams Weknora-style RAG stages

- **WHEN** a user sends a `/chat/stream` request with `chat_mode=quick` and the knowledge base has retrievable evidence
- **THEN** the stream includes public trace stages for question understanding, knowledge-base retrieval, evidence reading or citation preparation, answer synthesis, and completion
- **AND** the stream still includes the existing `sources`, `reasoning`, and answer `token` events
- **AND** the final answer is streamed from the quick RAG path, not from the reasoning-mode agent runtime

#### Scenario: Quick answer remains bounded

- **WHEN** quick mode emits execution trace events
- **THEN** the trace MUST be derived from the current retrieval, source extraction, context-building, and answer-generation data
- **AND** the trace MUST NOT require web search, ReAct loops, executable skills, or unavailable runtime tools

### Requirement: Trace summaries are safe for users

The system SHALL expose only audit-safe summaries in quick-mode trace events.

#### Scenario: Public thinking does not reveal private reasoning

- **WHEN** the quick trace includes a synthesis or thinking stage
- **THEN** the stage summary describes public evidence organization
- **AND** the payload MUST NOT include chain-of-thought, scratchpad, private reasoning, raw prompts, secrets, memory context, or unbounded provider payloads

#### Scenario: No evidence is handled explicitly

- **WHEN** quick mode retrieves no usable knowledge-base evidence
- **THEN** the trace includes a retrieval or completion status that indicates insufficient evidence
- **AND** the answer tells the user that the provided documents cannot determine the answer instead of inventing facts

### Requirement: Quick trace is frontend-compatible

The system SHALL keep the existing chat SSE contract compatible while improving quick-mode trace detail.

#### Scenario: Existing clients continue to parse the stream

- **WHEN** a client understands the existing `sources`, `reasoning`, `agent_trace`, `token`, and `[DONE]` events
- **THEN** it can parse a quick-answer stream without a protocol migration
- **AND** any new trace fields are additive and optional

#### Scenario: Bee timeline shows meaningful quick progress

- **WHEN** the Bee frontend receives the quick-mode trace
- **THEN** it renders user-facing progress equivalent to "理解问题", "检索知识库", "引用了 N 篇文档", "思考", and "完成"
- **AND** it does not imply non-existent tool calls when quick mode only used the bounded RAG path
