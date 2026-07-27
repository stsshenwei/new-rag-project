## Why

Quick answer and intelligent reasoning currently use different backend execution paths, which makes their SSE events, timeline behavior, completion guarantees, and answer-shaping rules drift over time. This change proposes a Weknora-inspired unified runtime where both modes share the same ReAct loop and event contract, while mode-specific policy and prompts keep quick answers fast and reasoning answers deep.

## What Changes

- Introduce a common chat runtime execution model: `Execute -> executeLoop -> runReActIteration`.
- Model each iteration as `Think -> Analyze -> Act -> Observe`, with the stop condition based on model response/tool-call analysis.
- Add explicit runtime policies for `quick` and `reasoning` instead of maintaining separate raw and agentic streaming paths.
- Route all mode output through the same domain event stream, including query, thought, tool call, tool result, reflection, references, final answer, completion, and error events.
- Add a lightweight EventBus/stream handler boundary so the runtime emits domain events and the SSE layer only subscribes/translates them.
- Guarantee completion/error lifecycle events even when the runtime exits early, fails, or the client disconnects.
- Preserve quick-answer latency by using a low-iteration, answer-first policy rather than forcing full multi-round reasoning.
- Preserve backward-compatible SSE payloads for existing frontend consumers while making the domain event contract primary.

## Capabilities

### New Capabilities

- `unified-react-chat-runtime`: Defines the shared Execute/loop/iteration model for quick and reasoning chat modes.
- `chat-runtime-policies`: Defines mode-specific policies for quick and reasoning behavior, including prompts, tools, iteration limits, retrieval posture, and stop conditions.
- `agent-event-bus-streaming`: Defines runtime event publication/subscription, SSE stream handling, completion guarantees, and streaming-vs-snapshot event semantics.
- `quick-answer-runtime-parity`: Defines the expected quick-answer behavior when it runs through the unified runtime without becoming slow or over-agentic.

### Modified Capabilities

- None.

## Impact

- Backend chat streaming route: `backend/app/main.py`.
- Backend agent execution: `backend/app/services/agent_runtime.py`.
- Runtime tool registry and tool schemas: `backend/app/services/agent_runtime_tools.py`.
- Runtime event models: `backend/app/models/agent_runtime.py`.
- Prompt templates and policy configuration: `backend/config/prompt_templates/`.
- Frontend SSE parsing and timeline rendering: `frontend/app/chat/page.tsx`, `frontend/app/lib/agent-stream.ts`, and `frontend/app/components/AgentTimeline.tsx`.
- Design docs and validation coverage for backend RAG pipeline and frontend chat UI.
