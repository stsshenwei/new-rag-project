## 1. Agent Models And Configuration

- [x] 1.1 Add models for query route, retrieval plan, planned tool, agent state, agent trace step, tool call, tool observation, evidence item, evidence bundle, verification result, and enterprise query response.
- [x] 1.2 Add configuration for `AGENTIC_RETRIEVAL_ENABLED`, trace streaming, max tool calls, tool timeouts, and per-tool result limits.
- [x] 1.3 Add tests for model serialization, safe defaults, and backwards-compatible response fields.

## 2. QueryRouter

- [x] 2.1 Add deterministic `QueryRouter` support for `fact`, `source`, `howto`, `troubleshooting`, `comparison`, `impact`, `dependency`, `summary`, and `decision`.
- [x] 2.2 Add route metadata for detected entities, requested sources, graph intent, and uncertainty.
- [x] 2.3 Add safe fallback routing for unknown or low-confidence questions.
- [x] 2.4 Add tests for every supported question type and fallback routing.

## 3. RetrievalPlanner

- [x] 3.1 Add `RetrievalPlanner` that maps routes to approved tools only.
- [x] 3.2 Enforce `fact` = Raw RAG + GraphRetriever entity search.
- [x] 3.3 Enforce `source` = Raw RAG only.
- [x] 3.4 Enforce `impact` and `dependency` require GraphRetriever path or neighbor retrieval.
- [x] 3.5 Enforce `troubleshooting` = Error/Config/Service graph + Raw RAG + Keyword Search.
- [x] 3.6 Add tests for deterministic tool plans, limits, and no arbitrary tools.

## 4. Tool Interfaces

- [x] 4.1 Add `RetrievalTool` protocol and shared tool result shape.
- [x] 4.2 Implement `RawRAGTool` using existing `RAGService.hybrid_retrieve_hits`, parent recall, and source extraction.
- [x] 4.3 Implement `KeywordSearchTool` using existing keyword search / SQLite FTS5 provider.
- [x] 4.4 Implement `GraphRetrieverTool` using `GraphRetriever.entity_search`, `neighbor_search`, and `path_search`.
- [x] 4.5 Add tests for each tool returning traceable evidence and not generating final answers.

## 5. Finite-State Workflow

- [x] 5.1 Add `AgenticRetrievalWorkflow` with explicit states: AnalyzeQuestion, PlanRetrieval, CheckPermissionScope, RunRetrieval, FuseEvidence, RerankEvidence, NeedMoreEvidence, BuildContext, GenerateAnswer, VerifyCitations, ReturnAnswer.
- [x] 5.2 Ensure tool calls happen only in RunRetrieval and only through planned approved tools.
- [x] 5.3 Add permission scope placeholder that can pass current single-tenant behavior and later enforce tenant/KB access.
- [x] 5.4 Add tests proving state order, no free-form tool loop, and safe fallback when a state fails.

## 6. Evidence Fusion And Sufficiency

- [x] 6.1 Add evidence fusion that deduplicates raw chunks, keyword chunks, graph entities, graph paths, and source chunk ids.
- [x] 6.2 Preserve source tool and query route metadata on each evidence item.
- [x] 6.3 Add evidence sufficiency rules for general, dependency, impact, and troubleshooting questions.
- [x] 6.4 Add tests proving dependency/impact questions are insufficient without graph path evidence.
- [x] 6.5 Add tests proving insufficient evidence returns explicit uncertainty.

## 7. CitationVerifier

- [x] 7.1 Add `CitationVerifier` for citations, used chunks, graph paths, and graph relation source chunks.
- [x] 7.2 Verify every citation and used chunk resolves through `DocumentRepository.get_chunk()`.
- [x] 7.3 Verify every graph path relation has a resolvable `source_chunk_id`.
- [x] 7.4 Block or downgrade factual answers when citation verification fails.
- [x] 7.5 Add tests for valid citations, invalid citations, missing graph source chunks, and verification trace summaries.

## 8. Answer Generation And Enterprise Response

- [x] 8.1 Build agent context from fused evidence, graph context, and raw evidence without exposing hidden chain-of-thought.
- [x] 8.2 Generate final answers from verified evidence and preserve explicit insufficient-evidence behavior.
- [x] 8.3 Extend `/rag/query` to return enterprise fields: `agent_trace`, `tool_calls`, and `evidence_summary` in addition to existing response fields.
- [x] 8.4 Ensure default-disabled agentic retrieval preserves existing `/rag/query` behavior.
- [x] 8.5 Add API tests for fact, source, dependency, troubleshooting, insufficient evidence, and citation failure responses.

## 9. Workbuddy Trace And Streaming

- [x] 9.1 Add visible trace steps for question analysis, planning, tool call start, tool observation, evidence sufficiency, answer generation, and citation verification.
- [x] 9.2 Ensure trace summaries do not include hidden chain-of-thought or private scratchpad text.
- [x] 9.3 Wire optional `/chat/stream` agent trace payloads behind configuration.
- [x] 9.4 Preserve existing `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` SSE behavior.
- [x] 9.5 Add route tests for trace event ordering, simple client compatibility, and disabled trace behavior.

## 10. Supersede Question Decomposition

- [x] 10.1 Update `add-agent-question-decomposition` artifacts or docs to indicate it is superseded by `add-agentic-retrieval-workflow`.
- [x] 10.2 Reuse its visible reasoning trace concepts in the new trace model.
- [x] 10.3 Do not implement the older change separately as part of this work.

## 11. Documentation

- [x] 11.1 Update `docs/ARCHITECTURE.md` with the Agentic Retrieval Layer and FSM diagram.
- [x] 11.2 Update `docs/design-docs/backend-rag-pipeline.md` with query routing, tool planning, evidence fusion, and citation verification.
- [x] 11.3 Update `docs/DEVELOPMENT.md` with agentic retrieval environment variables and validation commands.
- [x] 11.4 Update API documentation or README notes for the enterprise `/rag/query` response fields.

## 12. Validation

- [x] 12.1 Run backend unit tests for router, planner, tools, FSM workflow, evidence fusion, citation verifier, and API compatibility.
- [x] 12.2 Run chat stream API tests for optional trace and backwards-compatible SSE.
- [x] 12.3 Run a fake-provider smoke test covering fact, source, dependency, troubleshooting, insufficient evidence, and citation failure flows.
- [x] 12.4 Run full backend regression tests.
