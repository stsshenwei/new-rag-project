## 1. Event Contract Foundation

- [x] 1.1 Add typed Agent domain event names, statuses, common payload fields, and serialization helpers in the backend runtime model layer.
- [x] 1.2 Add sanitization tests proving domain events remove chain-of-thought, scratchpads, raw prompts, memory context, provider payloads, secrets, and unbounded raw tool payloads.
- [x] 1.3 Add ordering tests for a normal sourced reasoning lifecycle: query, thought, tool call, tool result, reflection, references, final answer, complete.
- [x] 1.4 Add backend helpers that convert existing trace/tool payloads into domain events without changing old event consumers.

## 2. Agent Runtime Domain Events

- [x] 2.1 Emit `agent_query` when reasoning-mode runtime starts processing the user question.
- [x] 2.2 Emit `agent_thought` public audit summaries at safe runtime checkpoints before and after retrieval decisions.
- [x] 2.3 Emit `agent_tool_call` and `agent_tool_result` for all runtime tool executions while preserving existing `tool_call` and `tool_observation` compatibility data.
- [x] 2.4 Emit `agent_references` before final answer tokens when traceable citations exist.
- [x] 2.5 Emit `agent_final_answer`, `agent_complete`, and `agent_error` events with compatible final metadata and predictable completion behavior.
- [x] 2.6 Update runtime loop tests for event order, failure handling, max-iteration fallback, and old client compatibility.

## 3. Structured Thinking And Reflection

- [x] 3.1 Extend the `thinking` tool or controller-produced thought payload to support `phase`, `summary`, `validity`, `gap`, `correction_query`, `completion_status`, and source chunk ids.
- [x] 3.2 Add `agent_reflection` emission after initial deep-read evidence is available.
- [x] 3.3 Add tests proving thought/reflection payloads are user-safe audit summaries and do not expose hidden chain-of-thought.
- [x] 3.4 Update prompt guidance so the Agent reports public evidence status and correction queries through the structured thought/reflection contract.

## 4. Reflective Remedial Retrieval

- [x] 4.1 Add runtime state for remedial attempt count, previous candidate ids, previous deep-read ids, reflection gaps, and correction queries.
- [x] 4.2 Trigger a bounded remedial retrieval pass when reflection identifies a repairable evidence gap and attempts remain.
- [x] 4.3 Emit `agent_remedial_search` with gap, correction query, attempt number, selected tools, and sanitized result metadata.
- [x] 4.4 Deduplicate remedial candidates against previously searched and deep-read chunks before adding them to evidence.
- [x] 4.5 Deep-read newly selected remedial chunks before final synthesis.
- [x] 4.6 Stop with an insufficient-evidence answer when remedial attempts are exhausted or no repairable correction query exists.
- [x] 4.7 Add backend tests for successful remedial retrieval, duplicate-only remedial results, exhausted attempts, no correction query, and quick-mode isolation.

## 5. Chat SSE Compatibility

- [x] 5.1 Centralize mapping from Agent domain events to existing `/chat/stream` SSE payloads in the chat stream adapter.
- [x] 5.2 Preserve compatible `conversation_id`, `sources`, `token`, `final`, optional `memory_updated`, `error`, and `[DONE]` payloads for old clients.
- [x] 5.3 Ensure sourced reasoning responses emit `sources` before the first answer `token`.
- [x] 5.4 Prevent final metadata from causing old token-only clients to append the answer twice.
- [x] 5.5 Add route tests that consume only old SSE payloads and tests that consume the new additive Agent lifecycle payloads.
- [x] 5.6 Reconcile frontend/backend naming around `tool_result` versus `tool_observation`.

## 6. Frontend Timeline

- [x] 6.1 Extend frontend stream types for Agent domain event kinds and payload metadata.
- [x] 6.2 Normalize query, thought, reflection, remedial search, references, final answer, complete, and error events in `agent-stream.ts`.
- [x] 6.3 Pair tool calls and tool results by `call_id`, including remedial retrieval tool calls.
- [x] 6.4 Render public thought and reflection as process/evidence audit summaries, not private reasoning.
- [x] 6.5 Display remedial retrieval as a distinct follow-up search caused by an evidence gap.
- [x] 6.6 Derive final run summaries from domain events, including referenced document count, tool calls, elapsed time, insufficient status, and remedial retrieval usage.
- [x] 6.7 Add frontend normalizer and timeline tests for normal, remedial, insufficient, failed, unknown-event, and old-SSE-only streams.

## 7. Documentation And Validation

- [x] 7.1 Update `docs/design-docs/backend-rag-pipeline.md` with the Agent domain event lifecycle and remedial retrieval loop.
- [x] 7.2 Update `docs/design-docs/frontend-chat-ui.md` with the new timeline event model and compatibility behavior.
- [x] 7.3 Add or update validation notes with representative Weknora-parity questions, including an answer that requires remedial retrieval.
- [x] 7.4 Run focused backend runtime/SSE tests.
- [x] 7.5 Run focused frontend stream normalizer/timeline tests.
- [x] 7.6 Run the frontend build or equivalent validation command.
