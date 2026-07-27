## 1. Runtime Policy Foundation

- [x] 1.1 Add a `ChatRuntimePolicy` model covering mode, prompt template ids, tool allowlist, max iterations, retry limits, retrieval posture, remedial behavior, and streaming options.
- [x] 1.2 Add policy resolution from the existing resolved chat mode, with safe defaults for quick and reasoning.
- [x] 1.3 Add environment configuration for unified runtime enablement and policy-specific overrides.
- [x] 1.4 Add validation that policy tool allowlists intersect with globally enabled tools before tools are exposed to the model.
- [x] 1.5 Add unit tests for quick and reasoning policy defaults, overrides, and invalid override fallback.

## 2. Event Bus And Domain Stream Boundary

- [x] 2.1 Add a request-scoped runtime event bus or equivalent explicit event stream abstraction.
- [x] 2.2 Define publish/subscribe APIs for domain events without exposing SSE-specific payloads to runtime phases.
- [x] 2.3 Add common event sequencing, run id propagation, timestamping, status handling, and payload sanitization at the event boundary.
- [x] 2.4 Add terminal lifecycle handling that guarantees `agent_complete` or `agent_error` emission for started runs when the stream remains writable.
- [x] 2.5 Add unit tests for event ordering, subscription cleanup, payload sanitization, and terminal event guarantee.

## 3. Shared ReAct Runtime Loop

- [x] 3.1 Extract or adapt `AgentRuntime.stream_query_events()` into shared `execute`, `execute_loop`, and `run_react_iteration` phases.
- [x] 3.2 Implement Think phase model calls using policy-provided prompts, tools, temperature, and tool-choice settings.
- [x] 3.3 Implement Analyze phase handling for tool calls, final answer eligibility, deep-read guards, empty retries, repeated responses, and iteration limits.
- [x] 3.4 Implement Act phase execution through the existing tool registry with policy allowlist enforcement.
- [x] 3.5 Implement Observe phase message-history updates from sanitized tool results.
- [x] 3.6 Preserve existing reasoning behavior for knowledge search, grep, deep read, reflection, bounded remedial retrieval, references, and final answer streaming.
- [x] 3.7 Add regression tests proving reasoning mode still emits the existing Agent domain event lifecycle.

## 4. Quick Policy Integration

- [x] 4.1 Add quick policy preloaded retrieval using the existing bounded RAG retrieval and source extraction path.
- [x] 4.2 Inject quick-mode evidence into the shared runtime prompt/context before the first model call.
- [x] 4.3 Configure quick mode to complete in one low-cost iteration when the model returns no tool calls.
- [x] 4.4 Disable reasoning-mode reflective remedial retrieval for quick policy by default.
- [x] 4.5 Emit quick-mode domain events for query, references when available, final answer content, completion, and errors.
- [x] 4.6 Add a feature flag to route quick mode through unified runtime while preserving rollback to `_stream_raw_chat_events()`.
- [x] 4.7 Add tests that quick mode uses the shared runtime but does not enter an open-ended tool loop.

## 5. SSE Stream Handler Compatibility

- [x] 5.1 Refactor `/chat/stream` SSE mapping so it subscribes to runtime domain events and translates them to `data: <json>` frames.
- [x] 5.2 Preserve legacy `conversation_id`, `sources`, `token`, `error`, `final`, and `[DONE]` behavior for existing clients.
- [x] 5.3 Ensure `agent_references` and compatible `sources` are emitted before the first answer token for sourced quick and reasoning responses.
- [x] 5.4 Ensure final metadata does not cause legacy clients to append duplicate answer text.
- [x] 5.5 Add route-level tests for quick and reasoning SSE event order, backward compatibility, and failure completion.

## 6. Frontend Timeline Parity

- [x] 6.1 Update frontend stream parsing to accept unified runtime events for both quick and reasoning messages.
- [x] 6.2 Update timeline normalization so quick mode can render a coherent completed timeline without tool events.
- [x] 6.3 Preserve reasoning timeline rendering for thoughts, tool calls, tool results, reflection, remedial retrieval, references, answer, and completion.
- [x] 6.4 Add UI labels or summaries that distinguish quick low-iteration execution from reasoning multi-step execution without exposing internals.
- [x] 6.5 Add frontend tests for quick event streams, reasoning event streams, unknown additive events, and no duplicate answer rendering.

## 7. Prompt And Documentation Updates

- [x] 7.1 Add or update quick and reasoning prompt templates to align with policy behavior and Markdown answer standards.
- [x] 7.2 Document the unified runtime architecture in the backend RAG pipeline design doc.
- [x] 7.3 Document frontend event/timeline expectations in the frontend chat UI design doc.
- [x] 7.4 Add validation notes covering quick latency, reasoning loop behavior, event ordering, and SSE compatibility.

## 8. Validation

- [x] 8.1 Run focused backend unit tests for runtime loop, policy resolution, event bus behavior, and chat stream routes.
- [x] 8.2 Run frontend agent-stream tests.
- [x] 8.3 Run frontend production build.
- [x] 8.4 Run `openspec validate "unify-chat-react-event-runtime" --strict`.
- [x] 8.5 Perform a manual smoke test for quick and reasoning chat modes against `/chat/stream`.
