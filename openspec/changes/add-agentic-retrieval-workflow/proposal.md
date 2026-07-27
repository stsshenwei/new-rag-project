## Why

Raw RAG, SQLite FTS5 keyword retrieval, and GraphRetriever now exist as separate evidence tools, but the query path still lacks a deterministic workflow for choosing and combining them. This change adds a finite-state agentic retrieval workflow that can route questions, call approved tools, verify citations, and show a workbuddy-style visible process without becoming a free-form Agent.

## What Changes

- Supersede the unimplemented `add-agent-question-decomposition` change with a broader, safer agentic retrieval workflow.
- Add `QueryRouter` for supported question types: `fact`, `source`, `howto`, `troubleshooting`, `comparison`, `impact`, `dependency`, `summary`, and `decision`.
- Add `RetrievalPlanner` to map question types to approved tools and retrieval strategies.
- Add tool interfaces for `RawRAGTool`, `KeywordSearchTool`, and `GraphRetrieverTool`.
- Add a finite-state workflow with stages: `AnalyzeQuestion`, `PlanRetrieval`, `CheckPermissionScope`, `RunRetrieval`, `FuseEvidence`, `RerankEvidence`, `NeedMoreEvidence`, `BuildContext`, `GenerateAnswer`, `VerifyCitations`, and `ReturnAnswer`.
- Add visible agent trace payloads that summarize question analysis, planned tools, tool execution, observations, evidence sufficiency, and citation verification without exposing hidden chain-of-thought.
- Extend `/rag/query` to return the enterprise answer format: answer, citations, graph paths, used entities, used chunks, confidence, agent trace, tool calls, evidence summary, and debug info.
- Keep `/chat/stream` backwards compatible while optionally emitting agent trace events.
- Add `CitationVerifier` to reject or downgrade factual answers whose citations cannot be resolved to `document_chunk`.
- Preserve Raw RAG as the safe fallback path and keep evidence-insufficient answers explicit.

## Capabilities

### New Capabilities

- `query-routing-planning`: Classify questions and choose approved retrieval tools for each question type.
- `agentic-retrieval-workflow`: Deterministic finite-state retrieval workflow combining Raw RAG, FTS5 keyword search, and GraphRetriever.
- `agent-tool-trace`: Workbuddy-style visible trace for analysis, planning, tool calls, observations, and verification without exposing hidden chain-of-thought.
- `citation-verification`: Citation and graph path verification against raw `document_chunk` evidence before returning factual answers.

### Modified Capabilities

- None.

## Impact

- Backend models: agent state, query route, retrieval plan, tool call, observation, evidence bundle, citation verification, and enterprise query response models.
- Backend services: new router, planner, tool wrappers, finite-state workflow, evidence fusion/checking, and citation verifier modules.
- Backend APIs: `/rag/query` gains enterprise response fields while preserving existing fields; `/chat/stream` may emit optional agent trace events while preserving existing SSE events.
- Retrieval: tool use varies by question type; `impact` and `dependency` require graph path retrieval, `source` remains Raw RAG only, and `troubleshooting` combines graph, Raw RAG, and FTS5.
- Safety: factual answers require resolvable citations; insufficient evidence returns a clear uncertainty answer.
- Prior changes: `complete-raw-evidence-layer`, `add-knowledge-graph-foundation`, and `add-graph-retriever` are prerequisites. The unimplemented `add-agent-question-decomposition` should not be implemented separately after this change unless it is refocused as a narrow UI-only follow-up.
