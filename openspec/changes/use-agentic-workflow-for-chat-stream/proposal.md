## Why

`/rag/query` can now use the finite-state Agentic Retrieval workflow, but `/chat/stream` still runs the older direct Raw RAG path and only emits an optional trace-like side event. This leaves the primary chat UI without the real workbuddy-style process the backend already knows how to execute.

## What Changes

- Add an agentic chat streaming path for `/chat/stream` behind configuration.
- Extend `AgenticRetrievalWorkflow` with a streaming event API so FSM states can emit SSE events as they execute.
- Use the same approved tools, evidence fusion, sufficiency checks, answer generation, and citation verification rules as `/rag/query`.
- Preserve existing chat memory behavior: `conversation_id`, recent conversation context, long-term memory context, assistant message persistence, summarization, and `memory_updated`.
- Preserve existing SSE compatibility: old clients still receive `conversation_id`, `sources`, `reasoning`, `token`, optional `memory_updated`, and `[DONE]`.
- Emit optional workbuddy-style events before answer tokens: `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, and `citation_verification`.
- Keep the feature default-disabled so current chat streaming behavior remains unchanged unless explicitly enabled.

## Capabilities

### New Capabilities

- `agentic-chat-stream`: `/chat/stream` can execute the finite-state Agentic Retrieval workflow instead of the direct Raw RAG path when configured.
- `chat-agent-sse-events`: `/chat/stream` can stream visible agent workflow events while preserving existing SSE client compatibility.

### Modified Capabilities

- None.

## Impact

- Backend API: `/chat/stream` gains a configurable agentic path and optional SSE event types.
- Backend services: `AgenticRetrievalWorkflow` needs a streaming event API that shares core FSM logic with non-streaming `/rag/query`.
- Backend memory flow: conversation and long-term memory handling must remain compatible with the agentic streaming answer path.
- Tests: add backend route and workflow tests for disabled behavior, enabled agentic flow, event ordering, tool observations, citation failure, memory update, and old-client compatibility.
- Frontend: no required UI change in this change; current SSE parser should continue to ignore unknown JSON fields. A later UI change can render these events as a process panel.
