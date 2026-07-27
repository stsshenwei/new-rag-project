## Context

The backend already has a finite-state `AgenticRetrievalWorkflow` used by `/rag/query` when `AGENTIC_RETRIEVAL_ENABLED=true`. That workflow routes the question, plans approved tools, runs retrieval tools, fuses evidence, checks sufficiency, generates an answer, verifies citations, and returns enterprise fields.

`/chat/stream` is still different. It currently performs Raw RAG directly in `backend/app/main.py`, emits `sources` and `reasoning`, optionally emits a lightweight `agent_trace`, then streams tokens from `RAGService.stream_answer()`. This preserves the old chat UI, but it does not actually execute the Agent FSM for chat.

This change selects option B from exploration: add a streaming event API to `AgenticRetrievalWorkflow` so `/chat/stream` can execute the same FSM and emit workbuddy-style progress as SSE events while preserving existing chat client compatibility.

## Goals / Non-Goals

**Goals:**

- Let `/chat/stream` use the same Agentic Retrieval FSM as `/rag/query` when configured.
- Stream state-level events while the workflow runs, not only after the workflow finishes.
- Preserve old SSE events and ordering expectations for existing frontend clients.
- Preserve conversation and memory behavior around the streamed answer.
- Keep graph usage optional; chat agent mode must still work when GraphRetriever is disabled.
- Keep citations strict: no factual final answer when citation verification fails.

**Non-Goals:**

- Do not introduce a free-form Agent or LangChain AgentExecutor.
- Do not expose hidden chain-of-thought.
- Do not require Neo4j to enable agentic chat streaming.
- Do not build a new frontend process panel in this change.
- Do not reimplement the older `add-agent-question-decomposition` change.

## Decisions

### Decision 1: Add `stream_query_events()` to `AgenticRetrievalWorkflow`

Add a streaming method that yields structured events as the FSM executes:

```text
AnalyzeQuestion -> PlanRetrieval -> CheckPermissionScope -> RunRetrieval
-> FuseEvidence -> RerankEvidence -> NeedMoreEvidence -> BuildContext
-> GenerateAnswer -> VerifyCitations -> ReturnAnswer
```

The non-streaming `run_query()` remains available for `/rag/query`. The implementation should share helper methods or a common execution state so chat streaming and `/rag/query` cannot drift into two different Agent behaviors.

Alternative considered: call `run_query()` first and emit all trace events after completion. Rejected because the user explicitly wants a workbuddy-style process that appears as work happens.

### Decision 2: Keep final answer token streaming

During `GenerateAnswer`, `stream_query_events()` should yield token events as `RAGService.stream_answer()` produces them. It must also collect the full answer text so conversation persistence and memory extraction can still run after streaming completes.

If evidence is insufficient or citation verification must block the answer, the stream should emit an explicit insufficient-evidence message as tokens or as a compatible final answer stream, not return an unsupported factual answer.

Alternative considered: return a complete answer without tokens in agentic chat mode. Rejected because `/chat/stream` exists to stream tokens and current clients expect token events.

### Decision 3: Add a separate chat enable flag

Use `CHAT_AGENTIC_WORKFLOW_ENABLED=false` as the chat-specific gate. `AGENTIC_RETRIEVAL_ENABLED` can remain the `/rag/query` gate.

This lets operators enable enterprise `/rag/query` first, then enable chat streaming after validating UX and latency. A deployment may set both to true when ready.

Alternative considered: reuse only `AGENTIC_RETRIEVAL_ENABLED`. Rejected because chat streaming has extra compatibility, latency, and memory implications.

### Decision 4: Preserve old SSE compatibility

Existing clients must continue to work by reading known JSON fields and ignoring unknown fields. The agentic chat path still emits:

- `conversation_id` before retrieval events
- `sources` before answer tokens
- `reasoning` before answer tokens
- `token` events for the answer
- optional `memory_updated`
- `[DONE]`

New optional events may be emitted before tokens:

- `agent_trace`
- `tool_call`
- `tool_observation`
- `evidence_summary`
- `citation_verification`

Alternative considered: replace `reasoning` with `agent_trace`. Rejected because the existing frontend and tests already use `reasoning`.

### Decision 5: Keep memory outside retrieval evidence

Conversation context and memory context should be passed into answer generation, but memory must not become a citation source or raw evidence item. Retrieved document chunks and graph source chunks remain the only citable evidence.

The route handler remains responsible for:

- creating or loading the conversation
- appending the user message
- recalling memory when enabled
- persisting assistant answer after completion
- summarizing conversation
- processing memory updates

The workflow is responsible for retrieval, evidence, verification, and answer token generation.

## Risks / Trade-offs

- Streaming FSM can duplicate non-streaming logic -> share helper methods and add parity tests between `/rag/query` and chat agent mode.
- Citation verification currently happens after generation -> for streaming, invalid citations may be discovered after tokens are emitted. Mitigate by verifying candidate evidence before generation and verifying final response metadata after generation; if final verification fails, stream an explicit correction/insufficient-evidence message before completion.
- Agentic chat increases latency before first token -> emit trace/tool events before tokens so users see progress.
- Existing frontend may ignore useful new events -> acceptable for this backend change; later UI work can render a process panel.
- GraphRetriever may be disabled -> graph tool observations should be `skipped` or empty, and dependency/impact questions should report insufficient graph evidence rather than failing the stream.

## Migration Plan

1. Add event models for agent stream events or reuse existing trace/tool call models with a typed SSE envelope.
2. Refactor `AgenticRetrievalWorkflow` so `run_query()` and `stream_query_events()` share route, plan, tool execution, fusion, sufficiency, context, and verification logic.
3. Add `CHAT_AGENTIC_WORKFLOW_ENABLED` and any chat-specific stream configuration.
4. Update `/chat/stream` to branch to agentic streaming only when the chat flag is enabled and workflow is available.
5. Keep the existing Raw RAG chat stream as the rollback path.
6. Add tests for disabled behavior, enabled event ordering, tool events, citation failure, memory compatibility, and old-client compatibility.

Rollback is configuration-only: set `CHAT_AGENTIC_WORKFLOW_ENABLED=false` to restore the existing Raw RAG chat stream.

## Open Questions

- Should `CHAT_AGENTIC_WORKFLOW_ENABLED=true` require `AGENTIC_RETRIEVAL_ENABLED=true`, or should it construct the workflow whenever either flag is enabled? Recommended: construct workflow when either flag is enabled, but keep each route gated separately.
- Should agentic chat emit both `reasoning` and `agent_trace`, or make `reasoning` a compact summary derived from agent evidence? Recommended: emit both for compatibility; derive `reasoning` from fused evidence when agentic chat is enabled.
- Should the frontend render agent events immediately in this change? Recommended: no, keep this backend-only and add UI rendering later.
