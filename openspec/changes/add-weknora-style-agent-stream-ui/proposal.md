## Why

The backend can now run the finite-state Agent workflow for chat and emit trace/tool/citation events, but the frontend still presents those events as a plain debug-like panel. WeKnora demonstrates a better product pattern: normalize agent stream events into a readable timeline with running/completed state, tool-result summaries, elapsed time, and citation status.

## What Changes

- Normalize existing chat SSE events into a stable frontend agent event stream model.
- Replace the current plain `AgentProcessPanel` with a WeKnora-style timeline for agentic chat.
- Show top-level run status such as running/completed/partial/failed, completed step count, total step count, and elapsed time.
- Pair tool call and tool observation events into a single user-readable timeline step.
- Render user-facing step labels for analysis, planning, permission check, retrieval tools, evidence fusion, sufficiency check, context building, answer generation, citation verification, and final return.
- Show compact tool-result summaries for Raw RAG, Keyword Search, GraphRetriever, evidence fusion, and citation verification.
- Preserve existing `/chat/stream` SSE compatibility, `sources`, `reasoning`, token streaming, memory updates, and feedback UI.
- Do not expose hidden chain-of-thought; display only safe trace summaries and tool metadata.
- Do not change Agent routing, retrieval planning, KG retrieval logic, or authentication behavior in this change.

## Capabilities

### New Capabilities

- `agent-stream-event-normalization`: Stable frontend event stream model that normalizes existing chat SSE payloads into safe agent events and derived timeline steps.
- `agent-stream-timeline-ui`: WeKnora-style chat timeline UI for progress, tool calls, observations, evidence summaries, citation checks, elapsed time, and final status.

### Modified Capabilities

- None.

## Impact

- Frontend chat message types gain normalized agent stream, timeline, summary, status, and elapsed-time fields.
- Frontend `/chat/stream` parser gains event normalization for `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, `citation_verification`, and final events.
- Chat UI gains a dedicated timeline component and replaces or de-emphasizes the current debug-like `AgentProcessPanel`.
- CSS gains timeline, step, running, completed, skipped, failed, collapsed, and compact mobile styles.
- Backend may add optional timestamp, event id, and final summary metadata to existing SSE payloads if needed, while preserving old event names.
- Tests need coverage for event normalization, paired tool call/result behavior, final status, elapsed time, and no chain-of-thought leakage.
