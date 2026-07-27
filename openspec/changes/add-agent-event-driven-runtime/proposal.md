## Why

Bee already streams chat progress through SSE, but the current event shape is an implementation-level mix of `agent_trace`, `tool_call`, `tool_observation`, `sources`, `token`, `final`, and `[DONE]`. It does not yet model the Weknora-style Agent lifecycle as first-class domain events, so visible thinking/reflection, remedial retrieval, reference-before-answer ordering, and frontend timeline behavior remain inconsistent.

This change introduces a dedicated Agent event-driven runtime contract so reasoning mode can show a clear, user-safe process: query, public thought, tool call, tool result, reflection, bounded remedial retrieval, references, final answer, and completion.

## What Changes

- Add a typed backend Agent event contract for query, public thought, tool calls, tool results, reflection, remedial search, references, final answer, completion, and error states.
- Adapt `AgentRuntime` to emit domain events in a stable order while preserving existing SSE payload compatibility for old clients.
- Extend the `thinking` behavior from a plain summary tool into user-safe structured thought/reflection payloads that can describe validity, evidence gaps, correction queries, and completion status without exposing hidden chain-of-thought.
- Add a bounded remedial retrieval loop that can trigger a second retrieval/deep-read pass when reflection identifies missing evidence.
- Ensure sourced answers emit references before final answer tokens in reasoning mode.
- Normalize new Agent events in the frontend timeline so users see Weknora-like stages instead of raw implementation labels.
- Keep quick-answer mode deterministic and low-latency; this change targets reasoning/Agent runtime behavior, with quick mode only receiving compatibility-safe event normalization if needed.

## Capabilities

### New Capabilities

- `agent-event-contract`: Defines the first-class Agent domain event taxonomy, required payload fields, ordering constraints, and user-safety rules.
- `reflective-remedial-retrieval`: Defines reflection-driven evidence validation and bounded remedial retrieval after initial search/deep-read results.
- `agent-sse-compatibility`: Defines how domain events map to existing `/chat/stream` SSE payloads without breaking `sources`, `token`, `final`, or `[DONE]` clients.
- `agent-timeline-events`: Defines frontend normalization and display behavior for query, thought, reflection, tool, references, answer, and completion events.

### Modified Capabilities

- None.

## Impact

- Backend event model: `backend/app/models/agent_runtime.py`
- Agent runtime orchestration: `backend/app/services/agent_runtime.py`
- Runtime tools and thinking payloads: `backend/app/services/agent_runtime_tools.py`
- Chat stream adapter: `backend/app/main.py`
- Frontend stream types and normalizer: `frontend/app/lib/types.ts`, `frontend/app/lib/agent-stream.ts`
- Frontend timeline component: `frontend/app/components/AgentTimeline.tsx`
- Tests: backend Agent runtime loop/SSE tests and frontend event normalization/timeline tests
- Documentation: backend RAG pipeline and frontend chat UI design docs
