## Context

The backend now has three evidence tools:

- Raw Evidence Layer: parent-child chunks, Milvus dense retrieval, SQLite FTS5 keyword retrieval, citations, and raw chunk lookup.
- Knowledge Graph Foundation: extracted entities, mentions, entity vectors, and evidence-bound graph relations.
- GraphRetriever: read-only entity search, neighbor search, path search, graph context building, and source chunk validation.

The missing layer is a deterministic Agent workflow that can choose the right evidence tools for a user question, combine their results, verify citations, and return an enterprise-grade answer. The previous `add-agent-question-decomposition` change focused on decomposition and frontend trace UI. This change supersedes it with a broader finite-state retrieval workflow. Decomposition can later be reintroduced as one planner strategy, but it should not be implemented as a separate first-class change now.

## Goals / Non-Goals

**Goals:**

- Add a finite-state `AgenticRetrievalWorkflow` above existing retrieval services.
- Add `QueryRouter` for `fact`, `source`, `howto`, `troubleshooting`, `comparison`, `impact`, `dependency`, `summary`, and `decision`.
- Add `RetrievalPlanner` to select approved tools by question type.
- Add tool interfaces and wrappers for Raw RAG, SQLite FTS5 keyword search, and GraphRetriever.
- Add visible workbuddy-style trace events for analysis, planning, tool calls, observations, evidence sufficiency, and citation verification.
- Add evidence fusion, reranking integration, and evidence sufficiency checks.
- Add `CitationVerifier` that verifies citations and graph path source chunks against `document_chunk`.
- Extend `/rag/query` with enterprise response fields while preserving existing fields.
- Allow `/chat/stream` to emit optional agent trace events without breaking existing SSE clients.

**Non-Goals:**

- Do not implement a free-form autonomous Agent.
- Do not allow arbitrary tools or model-decided external actions.
- Do not expose hidden chain-of-thought.
- Do not allow factual answers with missing or unresolvable citations.
- Do not remove or weaken the existing Raw RAG path.
- Do not build a full frontend graph visualization in this change.
- Do not implement complex graph community summaries in this change.

## Decisions

### Decision 1: Use a finite-state workflow, not a free Agent

Implement explicit states:

```text
START
  -> AnalyzeQuestion
  -> PlanRetrieval
  -> CheckPermissionScope
  -> RunRetrieval
  -> FuseEvidence
  -> RerankEvidence
  -> NeedMoreEvidence
  -> BuildContext
  -> GenerateAnswer
  -> VerifyCitations
  -> ReturnAnswer
END
```

Each state receives and returns typed state data. Tool calls are allowed only in `RunRetrieval`, and only through approved tool interfaces.

Rationale: The user explicitly wants a finite-state Agent and not a free-form Agent. This makes behavior testable, auditable, and safer for enterprise knowledge retrieval.

Alternative considered: let an LLM choose arbitrary tools in a loop. This was rejected because it is harder to test, harder to permission, and easier to hallucinate unsupported facts.

### Decision 2: Route first, then plan tools

`QueryRouter` classifies the question type and extracts high-level routing metadata. `RetrievalPlanner` maps that route to tools.

Default tool policy:

| Type | Tools |
|---|---|
| `fact` | Raw RAG + GraphRetriever entity search |
| `source` | Raw RAG only |
| `howto` | Raw RAG + Keyword Search |
| `troubleshooting` | GraphRetriever Error/Config/Service graph + Raw RAG + Keyword Search |
| `comparison` | Raw RAG + GraphRetriever entity search or neighbors |
| `impact` | GraphRetriever neighbor/path + Raw evidence |
| `dependency` | GraphRetriever path search required |
| `summary` | Raw RAG; future graph community summary optional |
| `decision` | Raw RAG + graph context + explicit uncertainty |

Rationale: separating route from plan keeps classification testable and makes the planner deterministic.

Alternative considered: have one planner LLM produce a free-form plan. This was rejected because tool requirements such as dependency requiring KG path should be deterministic.

### Decision 3: Treat tools as evidence providers, not answer generators

`RawRAGTool`, `KeywordSearchTool`, and `GraphRetrieverTool` return structured evidence bundles. They do not generate final answers.

Rationale: final answer generation should happen once after evidence fusion, sufficiency checking, context building, and citation verification.

Alternative considered: let each tool summarize its result. This was rejected because it would create multiple generation surfaces and make citation verification weaker.

### Decision 4: Visible trace is an audit summary

The workflow emits `agent_trace` steps and optional SSE trace events. Trace content includes:

- state name
- status
- user-facing summary
- planned tool names
- tool call metadata
- observation summary
- source chunk ids
- evidence sufficiency result
- citation verification result

Trace content must not include hidden chain-of-thought or raw private model reasoning.

Rationale: This gives the workbuddy-style experience the user wants while staying safe and controllable.

Alternative considered: stream hidden reasoning text. This was rejected for safety, privacy, and product correctness.

### Decision 5: Citations are a hard gate for factual answers

`CitationVerifier` runs after answer generation. It verifies:

- answer citations resolve to `document_chunk`
- `used_chunks` exist in `document_chunk`
- graph path relations have `source_chunk_id`
- graph path source chunks resolve to `document_chunk`

If verification fails for a factual answer, the workflow must downgrade to an insufficient-evidence answer or retry generation with valid evidence only.

Rationale: enterprise knowledge answers must be auditable. Graph facts are derived evidence and must remain tied to raw chunks.

Alternative considered: warn in debug metadata but still return the answer. This was rejected because it allows unsupported facts to reach users.

### Decision 6: Keep `/chat/stream` backwards compatible

Existing SSE payloads remain:

- `conversation_id`
- `sources`
- `reasoning`
- `token`
- `memory_updated`
- `[DONE]`

Optional new payloads may include:

- `agent_trace`
- `agent_step`
- `tool_call`
- `tool_observation`
- `citation_verification`

Existing clients that ignore unknown JSON fields should still work.

Rationale: frontend and users depend on current streaming behavior. Agent trace should enrich, not break.

### Decision 7: Supersede question decomposition

The existing unimplemented `add-agent-question-decomposition` should not be implemented separately. Its useful concepts become part of this change:

- visible reasoning trace -> `agent-tool-trace`
- decomposition -> future planner strategy, not MVP requirement
- frontend reasoning panel -> later UI follow-up if needed

Rationale: implementing both would create overlapping agent layers and duplicate SSE/event semantics.

## Risks / Trade-offs

- Agent workflow increases latency -> Keep feature default-disabled or configurable, enforce tool and path limits.
- Tool selection can be wrong -> Use deterministic planner rules and add tests per question type.
- Graph evidence may be sparse -> EvidenceChecker must allow explicit uncertainty and Raw RAG fallback where policy permits.
- Citation verification may reject many answers initially -> Start strict for factual claims and improve evidence formatting rather than weakening verification.
- SSE trace can confuse users -> Label it as process/evidence trace, not hidden thinking.
- `/rag/query` response shape grows -> Preserve existing fields and add optional enterprise fields.
- Older decomposition change remains active -> Mark it superseded in docs/tasks or avoid applying it separately.

## Migration Plan

1. Add agent models, trace models, and tool result models.
2. Add `QueryRouter` with deterministic rules and optional LLM-compatible interface boundary.
3. Add `RetrievalPlanner` with fixed tool policies by question type.
4. Add `RawRAGTool`, `KeywordSearchTool`, and `GraphRetrieverTool`.
5. Add FSM workflow with state-by-state tests.
6. Add evidence fusion, reranking hook, sufficiency checking, and context building.
7. Add `CitationVerifier`.
8. Integrate `/rag/query` enterprise response behind safe defaults.
9. Add optional `/chat/stream` trace events while preserving old stream shape.
10. Update docs and mark `add-agent-question-decomposition` as superseded.

Rollback is simple: disable agentic retrieval and continue using Raw RAG query behavior. Raw evidence and graph data remain valid.

## Open Questions

- Should the first implementation enable agentic workflow by default for `/rag/query`, or require `AGENTIC_RETRIEVAL_ENABLED=true` until smoke-tested? Recommended: default-disabled during implementation, then enable deliberately.
- Should `/chat/stream` use agent workflow immediately or only expose it behind `AGENT_TRACE_STREAM_ENABLED`? Recommended: optional trace behind config.
- Should dependency/impact questions return an insufficient-evidence answer when GraphRetriever has no path, even if Raw RAG has related text? Recommended: yes for dependency/impact claims, with Raw RAG text as supporting context only.
