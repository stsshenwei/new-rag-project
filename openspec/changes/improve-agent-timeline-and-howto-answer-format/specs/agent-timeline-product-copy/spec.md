## ADDED Requirements

### Requirement: Productized agent timeline
The chat UI SHALL map normalized agent stream events into a user-facing process timeline.

#### Scenario: Problem understanding
- **WHEN** the timeline receives an analysis or question-routing event
- **THEN** it SHALL render a user-facing step such as `已完成问题理解`

#### Scenario: Knowledge-base search
- **WHEN** the timeline receives retrieval tool call or observation events
- **THEN** it SHALL render a user-facing step such as `检索知识库：[query]` or `找到 N 个结果`

#### Scenario: Citation count
- **WHEN** the timeline has citation or source data
- **THEN** it SHALL render a step such as `引用了 N 篇文档`

#### Scenario: Answer organization
- **WHEN** the timeline receives answer-generation or context-building events
- **THEN** it SHALL render a user-facing step such as `思考` or `整理答案`

#### Scenario: Completion
- **WHEN** the assistant answer is complete
- **THEN** it SHALL render a completion step such as `完成`

#### Scenario: Intelligent reasoning mode
- **WHEN** agentic chat events are present for an assistant message
- **THEN** the UI SHALL render the primary timeline as an intelligent-reasoning process rather than a raw debug trace

#### Scenario: Quick answer mode
- **WHEN** only Raw RAG source and token events are present
- **THEN** the UI SHALL preserve the quick-answer experience and SHALL NOT imply that multi-step agent reasoning occurred

### Requirement: Internal details remain secondary
The product timeline SHALL avoid exposing implementation names as primary visible text.

#### Scenario: Raw tool name hidden from primary title
- **WHEN** a normalized event contains a tool name such as `RawRAGTool`, `KeywordSearchTool`, or `GraphRetrieverTool`
- **THEN** the primary timeline title SHALL use user-facing language rather than the raw class/tool name

#### Scenario: Tool names become public actions
- **WHEN** a normalized event contains `RawRAGTool`, `KeywordSearchTool`, or `GraphRetrieverTool`
- **THEN** the primary timeline SHALL map them to public actions such as `检索知识库`, `关键词检索`, or `查询图谱证据`

#### Scenario: Raw FSM stage hidden from primary title
- **WHEN** a normalized event contains an internal stage such as `FuseEvidence` or `NeedMoreEvidence`
- **THEN** the primary timeline title SHALL use user-facing language rather than the internal stage name

#### Scenario: Audit details preserved
- **WHEN** detailed normalized event metadata is available
- **THEN** the UI MAY keep it in secondary detail or tests, but primary text SHALL remain product-friendly

### Requirement: Private reasoning safety
The timeline SHALL display only public audit summaries and MUST NOT expose hidden model reasoning.

#### Scenario: Private fields are present
- **WHEN** event metadata contains `chain_of_thought`, `scratchpad`, `private_reasoning`, `raw_prompt`, or `memory_context`
- **THEN** those fields SHALL NOT appear in timeline titles, summaries, details, or rendered metadata

#### Scenario: Thinking step is displayed
- **WHEN** the UI displays a `思考` or answer-organization step
- **THEN** it SHALL describe public evidence-checking or answer-organization behavior, not hidden chain-of-thought
