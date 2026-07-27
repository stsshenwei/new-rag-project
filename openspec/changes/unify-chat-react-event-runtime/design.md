## Context

The current backend has two chat execution paths. Quick mode uses a direct raw RAG stream that retrieves evidence and streams answer tokens. Reasoning mode uses `AgentRuntime.stream_query_events()`, where the model can call tools across multiple iterations and the backend emits Agent domain events. This split makes quick mode fast, but it also means quick and reasoning can diverge in event coverage, completion semantics, source ordering, Markdown guidance, timeline rendering, and future retrieval improvements.

Weknora's useful pattern is not merely more event names; it is a shared execution engine where the runtime controls the loop and lifecycle events while prompts and policies drive mode behavior. The target shape is:

```text
Execute
  -> executeLoop
    -> runReActIteration
      -> Think
      -> Analyze
      -> Act
      -> Observe
```

Both quick and reasoning should flow through this shape, but quick policy must stay answer-first and low latency.

## Goals / Non-Goals

**Goals:**

- Use one runtime shell for quick and reasoning chat execution.
- Represent each run through stable domain events before conversion to SSE.
- Make quick and reasoning differ through `ChatRuntimePolicy` rather than route-level execution forks.
- Preserve quick mode's expected latency by avoiding open-ended ReAct loops.
- Preserve reasoning mode's ability to search, deep-read, reflect, and perform bounded remedial retrieval.
- Guarantee `agent_complete` or `agent_error` lifecycle emission even on early exits and failures.
- Keep `/chat/stream` backward compatible for clients that only consume `token`, `sources`, `error`, and `[DONE]`.

**Non-Goals:**

- Do not expose hidden chain-of-thought or private model scratchpads.
- Do not remove existing SSE compatibility payloads in this change.
- Do not force quick mode to perform multi-round tool-heavy reasoning.
- Do not introduce a complex distributed message broker; the event bus can be in-process and request-scoped.
- Do not change vector-store schema, document ingest, or knowledge-base storage behavior.

## Decisions

### Decision 1: Introduce A Shared Chat Runtime Shell

The backend will introduce a shared runtime abstraction that owns `execute()`, `execute_loop()`, and `run_react_iteration()`. Existing `AgentRuntime` behavior can be adapted into this shell rather than duplicated. The shell will emit domain events and return streamed answer content through the same event stream.

Alternative considered: Keep `_stream_raw_chat_events()` and `AgentRuntime.stream_query_events()` separate and only normalize frontend events. This is lower risk short term, but it keeps behavior drift in place and does not learn the main Weknora architectural lesson.

### Decision 2: Use Policy Objects For Mode Differences

Quick and reasoning modes will be selected through a `ChatRuntimePolicy` resolved from request mode. A policy controls prompt template id, allowed tools, max iterations, retrieval posture, completion rules, and whether preloaded evidence is injected before the first model call.

Recommended defaults:

```text
quick:
  max_iterations: 1-2
  tool_choice: none or restricted auto
  retrieval: preloaded top evidence
  remedial_retrieval: disabled
  prompt: answer-first, concise Markdown

reasoning:
  max_iterations: 6-10
  tool_choice: auto
  retrieval: model-driven tools
  remedial_retrieval: enabled and bounded
  prompt: ReAct, evidence-first
```

Alternative considered: Use only prompt text and keep all runtime configuration the same. This is flexible, but it allows accidental slow quick-mode behavior and makes latency/cost guardrails harder to enforce.

### Decision 3: Add A Request-Scoped EventBus Boundary

The runtime will publish domain events to a lightweight request-scoped event bus. The SSE handler subscribes to the bus and maps events to SSE payloads. In Python this can still be implemented as a generator-backed bus initially, but the boundary should be explicit:

```text
Runtime -> EventBus.Emit(domain_event)
SSE handler -> EventBus.On("*") -> serialize payload
Frontend -> normalize/render events
```

Alternative considered: Continue yielding SSE-shaped payloads directly from runtime code. This is simple, but it couples execution logic to transport details and makes it harder to test event lifecycle independently.

### Decision 4: Treat Streaming And Snapshot Events Differently

Thought and final answer content may be streamed in fragments. Query, tool calls, tool results, references, completion, and error events are snapshot events. The domain event model should include enough fields for both forms without making every event token-like.

Alternative considered: Convert every event to token streaming. That would simplify transport but reduce structured timeline fidelity and make tool/result events harder to audit.

### Decision 5: Completion Is A Runtime Lifecycle Guarantee

The runtime will guarantee a terminal event using a `try/finally`-style lifecycle. Normal completion emits `agent_complete`; fatal failures emit `agent_error` followed by terminal completion metadata when possible. The route still emits `data: [DONE]` as the SSE transport terminator.

Alternative considered: Emit completion only at normal generator end. That is fragile because exceptions, early breaks, and client disconnect handling can leave the frontend in a loading state.

### Decision 6: Quick Mode Uses Preloaded Evidence Instead Of Open-Ended Tooling

Quick mode will perform bounded retrieval before the first model call and include retrieved evidence in the prompt/context. The model can usually answer with `tool_calls=[]`, causing the same loop analyzer to stop immediately. Optional quick-mode tools can be introduced later, but the default must be no open-ended tool loop.

Alternative considered: Let quick mode use the same full tool set as reasoning. That improves flexibility but contradicts the user's latency expectation for quick answer.

## Risks / Trade-offs

- Runtime unification could increase quick-mode latency -> Keep quick policy bounded, preload evidence, and validate round count and time budget.
- EventBus abstraction could add complexity -> Start with an in-process request-scoped bus and avoid external brokers.
- Existing frontend clients might duplicate answer text -> Preserve existing token/final compatibility rules and keep final answer metadata from re-appending content.
- Prompt-driven tool choice can be unpredictable -> Enforce policy-level tool allowlists, iteration limits, deep-read guards, and remedial attempt limits in code.
- Completion guarantees can conflict with client disconnects -> Treat disconnect as transport cancellation while still closing local runtime spans and emitting terminal events when the stream is still writable.
- Existing tests target separate paths -> Add parity tests for quick and reasoning event order, SSE compatibility, and terminal events.

## Migration Plan

1. Introduce the runtime policy model and request-scoped event bus behind existing `/chat/stream`.
2. Adapt reasoning mode to publish through the bus while preserving current Agent domain events.
3. Add quick policy support using preloaded retrieval evidence and the shared analyzer/terminal lifecycle.
4. Route quick mode through the unified runtime behind a feature flag, while keeping the old raw path as rollback.
5. Update frontend normalization to treat quick and reasoning domain events consistently.
6. Validate quick latency, reasoning multi-round behavior, references-before-answer order, and completion/error terminal events.
7. Remove or deprecate the old raw stream path only after parity tests and manual smoke testing pass.

Rollback: disable the unified quick policy flag and route quick mode back to `_stream_raw_chat_events()` while leaving reasoning runtime unchanged.

## Open Questions

- Should quick mode expose a very small `thinking` event, or only query/references/final/complete to keep the timeline quiet?
- Should quick mode allow `grep_chunks` as an optional second iteration for exact-match misses, or keep all retrieval preloaded?
- What default quick latency budget should be enforced in tests: target round count, wall-clock budget, or both?
- Should `AgentRuntime` be renamed to a more general `ChatRuntime`, or should the existing name stay to reduce churn?
