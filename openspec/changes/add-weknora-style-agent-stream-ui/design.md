## Context

The project already has an Agentic Retrieval finite-state workflow and `/chat/stream` can emit agent events when `CHAT_AGENTIC_WORKFLOW_ENABLED=true`. Current frontend handling receives events such as `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, and `citation_verification`, but it renders them as a simple process/debug panel.

WeKnora's chat UI shows a more polished pattern: a normalized `agentEventStream`, a RAG pipeline progress timeline, thinking/progress blocks, paired tool call/result cards, completion state, elapsed time, and compact result summaries. This change adapts that product pattern to the existing Next.js frontend without replacing the backend Agent FSM.

## Goals / Non-Goals

**Goals:**

- Normalize existing chat SSE events into a stable frontend agent stream model.
- Derive timeline steps from normalized events instead of rendering raw event types directly.
- Show run status, completed steps, total steps, elapsed time, active/running step, failure/partial states, and citation verification status.
- Pair `tool_call` and `tool_observation` into one readable tool step.
- Provide safe user-facing labels and summaries for agent stages and tools.
- Render specialized compact summaries for Raw RAG, Keyword Search, GraphRetriever, evidence fusion, and citation verification.
- Preserve old `sources`, `reasoning`, `token`, memory, and feedback behavior.
- Keep hidden chain-of-thought private.

**Non-Goals:**

- No change to Agent routing, planning, retrieval algorithms, KG extraction, graph retrieval, or citation verification logic.
- No migration to LangChain Agent or free-form agent loops.
- No login, RBAC, tenant, or knowledge base permission UI.
- No full citation popover or chunk-preview drawer in this change.
- No Agent type preset configuration UI.
- No dependency on WeKnora code or UI libraries.

## Decisions

### Normalize In The Frontend First

The frontend will define a normalized model:

- `AgentStreamEvent`
- `AgentTimelineStep`
- `AgentRunSummary`

Existing SSE payloads will be converted into this model inside the chat stream handler. Backend event names remain compatible.

Rationale: The backend already emits enough events for a useful timeline. Frontend normalization avoids a backend contract break and allows iterative UI improvement.

Alternative considered: change backend to emit WeKnora-style `response_type` events directly. Rejected for this change because it would touch more tests and risk breaking existing `/chat/stream` clients.

### Pair Tool Calls With Observations

The timeline should not show separate noisy rows for `tool_call` and `tool_observation`. It should merge them by tool name/action/order into one step with status:

- `running` after `tool_call`
- `completed`, `failed`, or `skipped` after `tool_observation`

Rationale: Users care that a tool ran and what it found, not the raw protocol split.

Alternative considered: preserve one row per event. Rejected because it reads like logs rather than an assistant workflow.

### Render Safe Thinking As Trace Summaries

The UI will not display hidden chain-of-thought. It may render safe trace summaries already emitted by the deterministic FSM, such as "规划检索工具" or "证据足够，可以生成带引用回答".

Rationale: The user wants visible progress, but enterprise knowledge systems must not expose private scratchpads or model deliberation.

Alternative considered: add a real `thinking` stream. Rejected for this change because the current backend intentionally emits workbuddy-style public trace, not private reasoning.

### Add Optional Backend Metadata Only If Needed

If frontend-only timing is insufficient, backend events may add optional fields:

- `event_id`
- `created_at`
- `elapsed_ms`
- `sequence`
- final `run_summary`

All fields must be additive. Existing event names and payload shapes remain valid.

Rationale: Step count and elapsed time can be estimated client-side, but backend-provided metadata is more stable for final summaries and tests.

Alternative considered: require backend timestamps for every event. Rejected because it is not necessary for the MVP timeline.

### Keep Existing Reasoning Panel As Secondary

The WeKnora-style timeline becomes the primary process display. The existing `ReasoningPanel` remains available for legacy query-understanding details, but it should sit below or be visually secondary.

Rationale: `reasoning` currently contains retrieval query expansion and evidence previews that remain useful, but it is not the agent workflow itself.

## Risks / Trade-offs

- Timeline may appear empty when `CHAT_AGENTIC_WORKFLOW_ENABLED=false` -> show no timeline and keep the existing raw RAG reasoning panel.
- Tool call pairing may be ambiguous without ids -> pair by tool/action/order and prefer backend `event_id` if added later.
- Long source chunk ids can clutter the UI -> cap visible chips and show counts.
- Showing trace summaries could be mistaken for full reasoning -> label the panel as "可审计执行流" and document that hidden chain-of-thought is not exposed.
- Additional UI state can make chat parsing fragile -> isolate normalization into pure helper functions with tests.
- Mobile layout can become cramped -> provide compact collapsed default after completion and responsive wrapping.

## Migration Plan

1. Add normalized frontend types and pure normalizer helpers.
2. Update `/chat/stream` parsing to append normalized events while preserving old message fields.
3. Build a dedicated timeline component and replace the current process panel.
4. Add CSS for timeline tree, status header, step cards, running shimmer, completed/failed/skipped states, and mobile layout.
5. Optionally add backend event metadata only when needed for stable final summaries.
6. Add tests for event normalization and TypeScript checks.

Rollback strategy: disable or remove the timeline component and continue rendering existing `reasoning`, `sources`, and streamed tokens. Backend compatibility is preserved.

## Open Questions

- Should the timeline be expanded while running and collapsed after completion by default?
- Should the old `ReasoningPanel` remain visible by default, or be folded under an "检索详情" disclosure?
- Should final elapsed time come from frontend timestamps or backend `run_summary`?
- Should tool-specific result cards include top chunk previews in this change or stay as counts and short summaries?
