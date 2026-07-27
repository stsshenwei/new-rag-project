## ADDED Requirements

### Requirement: Finite-state workflow
The system SHALL implement agentic retrieval as a finite-state workflow.

#### Scenario: Workflow executes required states
- **WHEN** agentic retrieval is enabled for a query
- **THEN** the workflow SHALL execute `AnalyzeQuestion`, `PlanRetrieval`, `CheckPermissionScope`, `RunRetrieval`, `FuseEvidence`, `RerankEvidence`, `NeedMoreEvidence`, `BuildContext`, `GenerateAnswer`, `VerifyCitations`, and `ReturnAnswer`.

#### Scenario: No free-form tool loop
- **WHEN** the workflow runs
- **THEN** it SHALL NOT allow arbitrary model-selected tools outside the finite-state plan.

### Requirement: Tool execution
The system SHALL execute retrieval tools through stable tool interfaces.

#### Scenario: Raw RAG tool returns evidence
- **WHEN** `RawRAGTool` runs
- **THEN** it SHALL return traceable raw chunk evidence and citations.

#### Scenario: Keyword Search tool returns FTS evidence
- **WHEN** `KeywordSearchTool` runs
- **THEN** it SHALL return traceable keyword matches from SQLite FTS5 or the configured keyword provider.

#### Scenario: GraphRetriever tool returns graph evidence
- **WHEN** `GraphRetrieverTool` runs
- **THEN** it SHALL return structured entities, relations, graph paths, source chunk ids, and confidence.

### Requirement: Evidence fusion and sufficiency
The system SHALL fuse tool evidence and decide whether it is sufficient before final answer generation.

#### Scenario: Fuse evidence from multiple tools
- **WHEN** multiple tools return evidence
- **THEN** the workflow SHALL deduplicate and fuse evidence while preserving each evidence item source tool.

#### Scenario: Evidence insufficiency is explicit
- **WHEN** required evidence is missing or insufficient
- **THEN** the workflow SHALL return an answer that clearly states the system cannot determine the answer from available evidence.

#### Scenario: Dependency requires graph path evidence
- **WHEN** the question type is `dependency` and graph path evidence is missing
- **THEN** the workflow SHALL treat dependency evidence as insufficient even if Raw RAG returns related text.

### Requirement: Enterprise query response
The system SHALL return an enterprise answer format for agentic `/rag/query` responses.

#### Scenario: Query response contains enterprise fields
- **WHEN** `/rag/query` uses the agentic workflow
- **THEN** the response SHALL include `answer`, `citations`, `graph_paths`, `used_entities`, `used_chunks`, `confidence`, `agent_trace`, `tool_calls`, `evidence_summary`, and `debug_info`.

#### Scenario: Existing fields remain available
- **WHEN** `/rag/query` returns an agentic response
- **THEN** existing fields `answer`, `citations`, `used_chunks`, `used_entities`, `graph_paths`, `confidence`, and `debug_info` SHALL remain available for backwards compatibility.
