## Context

Bee has two visible chat execution paths today. Quick mode is a bounded Raw RAG path that emits `sources`, `reasoning`, optional `agent_trace`, answer `token`s, and `[DONE]`. Reasoning mode can use either the deterministic `AgenticRetrievalWorkflow` or the newer Weknora-style `AgentRuntime`, both of which emit trace and tool events through `/chat/stream`.

The existing event stream is useful but still implementation-shaped. It exposes generic payload keys such as `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, `citation_verification`, `sources`, `token`, and `final`. It does not provide a first-class Agent lifecycle equivalent to Weknora's query, thought, tool call, tool result, reflection, references, final answer, and completion events. It also lacks a deterministic reflection-driven remedial retrieval loop: the runtime can require deep reading after search, but it does not yet turn an identified evidence gap into a bounded second retrieval pass.

This design adds an Agent event-driven layer above the current runtime internals and below the SSE adapter. The domain layer becomes the product contract; the SSE layer remains backwards-compatible.

## Goals / Non-Goals

**Goals:**

- Introduce a typed Agent domain event model for reasoning mode.
- Emit a Weknora-like event order: query, public thought, tool call, tool result, reflection, optional remedial search, references, final answer, and completion.
- Preserve old `/chat/stream` clients that only understand `sources`, `token`, `final`, and `[DONE]`.
- Add structured, user-safe thought/reflection payloads without exposing hidden chain-of-thought.
- Add bounded remedial retrieval when reflection identifies missing evidence.
- Render the new events in the existing frontend timeline with clear product labels.

**Non-Goals:**

- Do not expose raw model reasoning, scratchpads, prompts, secrets, or unbounded tool outputs.
- Do not port Weknora code directly or require a Go-style global event bus.
- Do not change upload, parsing, chunking, Milvus schema, SQLite schema, or document storage.
- Do not force quick mode through the Agent runtime.
- Do not add web search, SQL, or external tools as part of this change.

## Decisions

### Decision: Add domain events, then adapt them to existing SSE payloads

The runtime should produce first-class domain events with stable names such as:

```text
agent_query
agent_thought
agent_tool_call
agent_tool_result
agent_reflection
agent_remedial_search
agent_references
agent_final_answer
agent_complete
agent_error
```

The chat stream adapter maps these to current SSE payloads where needed:

```text
agent_references    -> sources
agent_final_answer   -> token/final
agent_complete       -> [DONE]
agent_tool_call      -> tool_call
agent_tool_result    -> tool_observation
agent_thought        -> agent_thought plus compatible agent_trace
agent_reflection     -> agent_reflection plus compatible agent_trace
```

Rationale: this lets the frontend adopt the richer lifecycle while old clients keep working. It also avoids overloading `agent_trace` with every semantic event.

Alternative considered: rename all SSE payloads to Weknora-native event names. That would be cleaner internally but would break existing frontend tests, simple token clients, and prior OpenSpec compatibility guarantees.

### Decision: Treat public thought and reflection as audit summaries

`agent_thought` and `agent_reflection` are not hidden chain-of-thought. They are structured public status records:

```text
phase
summary
validity
gap
correction_query
completion_status
source_chunk_ids
```

The runtime may generate these through the existing `thinking` tool or through runtime controller checkpoints, but every emitted payload must be sanitized and bounded.

Alternative considered: stream model scratchpad text. That would appear closer to Weknora screenshots but is unsafe and conflicts with the project's trace sanitization rules.

### Decision: Put remedial retrieval in the runtime controller, not only the prompt

The model may decide to call more tools on its own, but Bee should not depend entirely on prompt obedience. After initial search and deep read, if reflection marks evidence as incomplete and provides a correction query, the runtime controller should allow a bounded remedial pass:

```text
initial search -> deep read -> reflection(gap)
  -> remedial search -> deep read remedial hits -> reflection(final check)
  -> references -> final answer
```

The controller must enforce attempt limits, dedupe previously read chunks, and stop with an insufficient-evidence answer when the gap remains.

Alternative considered: rely on low-recall query expansion in Raw RAG. That only reacts to low candidate count or score before evidence validation; it does not solve deep-read gap correction.

### Decision: References precede final answer tokens for sourced reasoning responses

For sourced reasoning answers, `agent_references` and compatible `sources` must be emitted before final answer tokens. The final payload can still include citations after token streaming for compatibility, but the user-visible reference event should not lag behind the answer.

Alternative considered: keep the existing runtime order where tokens can arrive before sources. That reduces refactoring but contradicts the desired Weknora-style flow and makes the UI look like it answers before evidence is settled.

### Decision: Frontend timeline consumes domain events and keeps generic fallback behavior

The frontend normalizer should understand the new Agent event kinds directly and map them into timeline steps. Unknown legacy or future events still fall back to generic `agent_trace` handling.

Tool calls and tool results should pair by `call_id`, and remedial retrieval should be visually distinct from the first retrieval pass without suggesting hidden reasoning is being exposed.

Alternative considered: create a separate Weknora-only timeline component. That would duplicate state logic and make quick/reasoning UI behavior drift.

## Risks / Trade-offs

- [Risk] More event types increase frontend/backend contract surface. -> Mitigation: define a single domain event schema and keep compatibility mapping centralized in the stream adapter.
- [Risk] Reflection could leak private reasoning. -> Mitigation: restrict emitted fields to public audit summaries and run payloads through existing sanitization.
- [Risk] Remedial retrieval can increase latency and token use. -> Mitigation: cap remedial attempts, cap tools per round, dedupe chunks, and make the final fallback explicit.
- [Risk] The model may provide poor correction queries. -> Mitigation: allow controller fallback to keyword/entity extraction from the original question and retrieved evidence metadata.
- [Risk] Event ordering changes can regress existing tests. -> Mitigation: add tests for old `sources`/`token` compatibility and new domain event order.
- [Risk] Quick mode could become slower if accidentally routed through this runtime. -> Mitigation: keep quick mode outside the domain event runtime except for additive UI normalization.

## Migration Plan

1. Add domain event models and serialization tests without changing `/chat/stream` behavior.
2. Add stream adapter mapping from domain events to existing SSE payloads behind reasoning mode.
3. Update `AgentRuntime` to emit query, thought, tool, result, references, final answer, and complete events in the new order.
4. Extend `thinking`/reflection payloads and add remedial retrieval controller logic with strict attempt limits.
5. Update frontend types, normalizer, and timeline rendering for the new event kinds.
6. Update backend/frontend tests and design docs.
7. Roll back by disabling `AGENT_RUNTIME_ENABLED` or falling back to the deterministic workflow while keeping old SSE events unchanged.

## Open Questions

- Should the public SSE event names use `agent_thought`/`agent_reflection`, or should they be nested under a single `agent_event` envelope?
- Should remedial retrieval default to one attempt, or should it be configurable with `AGENT_REMEDIAL_RETRIEVAL_MAX_ATTEMPTS`?
- Should quick mode eventually emit the same domain event taxonomy with a reduced subset, or remain on the existing quick trace stages?
