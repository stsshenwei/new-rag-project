## Context

The backend already implements a ReAct-style outer loop in `AgentRuntime`: each round sends the accumulated messages to the reasoning model, accepts zero or more tool calls, appends observations, and repeats until the model returns content without tool calls. The current default action limit is six rounds.

Three details make the practical flow more serial and less autonomous than that architecture suggests:

1. The prompt describes semantic retrieval as occurring after grep, which encourages one retrieval tool per model response even though the response schema accepts multiple calls.
2. The executor iterates through returned tool calls serially. Several read-only calls could overlap, but current tool implementations mutate shared `state` and retrieval-debug fields, so adding threads around the loop would introduce races.
3. A `thinking` gap currently causes controller code to perform a prescribed semantic search and deep read. That bypasses the next ReAct decision and treats newly read content as proof that the gap is resolved.

Observed `agent_runtime_spans` confirm that model turns, rather than local document reads, are the main cost. Recent completed runs range from roughly 14 to 99 seconds. Aggregate model rounds take approximately 6-22 seconds each, while grep is around one second and local full-content reads are usually tens of milliseconds. Semantic retrieval can itself take around ten seconds, so overlapping it with grep can also help, but eliminating unnecessary model rounds has the larger expected effect.

This change crosses runtime orchestration, tool contracts, provider adaptation, prompting, event streaming, tests, and observability. It must preserve tenant/knowledge-base scope, prompt confidentiality, evidence grounding, source ordering, and the existing frontend SSE contract.

## Goals / Non-Goals

**Goals:**

- Preserve a genuine model-directed ReAct loop in which observations determine later actions.
- Let one model response schedule all independent actions derivable from current observations.
- Execute safe calls concurrently without racing request state or global debug state.
- Retain grep-first, mandatory deep read, authorization, and evidence-sufficiency controls as guardrails.
- Remove default controller-selected remedial retrieval.
- Terminate predictably under repeated actions, call limits, and wall-clock limits.
- Stream terminal answers where provider semantics make that safe.
- Make model time, tool time, batching, fallback, and budget termination measurable.

**Non-Goals:**

- Building a fixed grep-to-vector-to-read composite pipeline.
- Precomputing or persisting a global synonym dictionary.
- Allowing a tool call to consume identifiers produced by another call in the same model response.
- Exposing private chain-of-thought or system prompts.
- Changing ingestion, vector schemas, knowledge-base authorization, or public HTTP routes.
- Guaranteeing that every question completes in a fixed number of rounds or a fixed latency.
- Raising the default iteration limit merely to imitate another implementation.

## Decisions

### 1. Keep the ReAct loop and change the unit of execution to an action batch

One LLM response is an `ActionBatch` containing the ordered tool calls returned by the model. A normal iteration becomes:

1. Call the model with accumulated observations and available tool schemas.
2. If no tool calls are returned, validate the answer and terminate.
3. Otherwise validate the complete batch, execute eligible calls, collect observations, and append them in declared order.
4. Let the next model turn decide what the observations imply.

Calls in a batch must be independent with respect to data. For example, grep and semantic search can share a batch because both derive arguments from the user question. A full-content read that requires a candidate ID returned by search must occur in a later batch.

Alternative considered: add a composite `search_and_read` tool or hard-code a three-stage pipeline. This saves model turns in a narrow happy path but prevents the model from adapting its query and read targets after seeing evidence, which is the behavior this change is intended to preserve.

#### Think phase versus `thinking` tool

The ReAct `Think` phase is the call to the LLM with conversation messages and function schemas. It is not a preliminary call to a tool named `thinking`. During that single inference the model can decide retrieval is necessary, formulate synonyms from parametric language knowledge, and directly return:

```text
tool_calls:
  - grep_chunks(query="风控系统|风控平台|风险控制|Enterprise.Risk.Control")
```

The optional `thinking` tool has a different responsibility: it publishes a concise user-safe plan or reflection status when explicit audit output is useful. Requiring it before every action would produce `LLM -> thinking tool -> LLM -> retrieval`, adding an unnecessary model round and making the runtime slower.

This matches the reference engine's actual control flow: its `runReActIteration` labels `callLLMWithRetry` as the Think step, while its prompt and agent presets describe the `thinking` tool as optional and leave it out of the default RAG tool set. The new runtime and UI terminology must preserve this distinction.

### 2. Interpret grep-first at the batch boundary

The first LLM inference owns intent assessment. Returning a retrieval tool call means retrieval is needed; returning a valid plain answer means it is not. The current `_requires_grep_first` keyword/regular-expression classifier will no longer act as a first-action planner.

When the LLM chooses knowledge-base retrieval, the first batch containing any retrieval action must contain `grep_chunks`. It may also contain `knowledge_search` or graph retrieval. The guard validates batch membership rather than requiring grep to finish before another retrieval starts, and it does not force a conversational response through grep merely because the text matches a broad lexical pattern.

The prompt will tell the model to place domain synonyms, aliases, translations, abbreviations, model fragments, and equivalent parameter expressions directly in tool arguments. It will also tell the model to batch independent searches that can be formulated now and avoid a standalone `thinking` call when it can select the action directly.

Alternative considered: generate variants or classify factual intent in controller code before retrieval. That reintroduces a fixed preprocessing stage, cannot incorporate aliases learned from observations, and grows into domain-specific rules.

### 3. Add explicit execution-safety metadata to tool registration

Each registered tool declares an execution class:

- `parallel_safe`: read-only or request-local operation whose result does not depend on another call in the batch.
- `serial`: operation requiring deterministic isolation from adjacent state updates.
- `exclusive`: operation with side effects or external constraints that cannot overlap any other call.

The scheduler validates every call first, then creates execution segments in original order. Contiguous `parallel_safe` calls run in a bounded `ThreadPoolExecutor`; a `serial` or `exclusive` call forms a barrier. The controller waits for all scheduled calls before making the next model request.

Initial expected classifications after state refactoring are:

| Tool | Class | Rationale |
| --- | --- | --- |
| `grep_chunks` | `parallel_safe` | Request-scoped read and returned delta |
| `knowledge_search` | `parallel_safe` | Request-scoped retrieval and debug result |
| `list_knowledge_chunks` | `parallel_safe` | Read-only when IDs are already known |
| `get_document_info` | `parallel_safe` | Read-only when document ID is known |
| `thinking` | `parallel_safe` | Audit observation and returned delta only |
| `todo_write` | `serial` | Ordered replacement/update semantics |
| Future mutating tools | `exclusive` by default | Conservative registration default |

Unknown tools default to non-executable; newly registered tools default to `exclusive` until explicitly classified.

Alternative considered: execute every returned call concurrently. Current shared mutations and future side-effecting tools make that unsafe.

### 4. Make tools return state deltas instead of mutating runtime state

Tool execution returns a `ToolExecutionResult` containing:

- model-visible content,
- structured evidence or candidate data,
- a typed `RuntimeStateDelta`,
- request-scoped debug and timing metadata,
- a structured error when execution fails.

Workers receive immutable request context and a state snapshot. They do not write to the shared state, event bus, or service-level `_last_retrieval_debug`. The controller merges successful deltas in original call order with field-specific reducers:

- candidate and deep-read IDs: stable ordered union,
- boolean completion flags: logical OR where monotonic,
- counters: additive,
- audit summaries: append with bounds,
- replace-style control fields: only from tools classified and executed serially.

Retrieval debug information becomes part of each tool result instead of a shared `RAGService` scratch field. This is required even when tool execution is configured as serial, because it removes hidden cross-request coupling.

Alternative considered: protect current mutation with one lock. A coarse lock would serialize most useful work and still leave ordering semantics implicit.

### 5. Preserve deterministic observations and event compatibility

Each call receives a stable batch ID, call ID, original index, and round number. Tool-start events are emitted in declared order. Workers report completion into a controller-owned queue; completion timestamps remain truthful, but model tool messages and final public step states are committed in original index order. The round-complete event is emitted only after every scheduled call is successful, failed, rejected, or cancelled.

A single independent-call failure becomes a structured tool observation so the LLM can adapt using other successful results. Authorization, scope, or global budget failures can stop remaining scheduling when continuing would be unsafe.

This keeps the existing domain-event and SSE envelope stable. New batch metadata is additive, so current frontend consumers can ignore it. Timeline reducers must mark completed parent steps even when children finish concurrently.

### 6. Keep evidence guards declarative and action-neutral

Candidate search results do not count as full answer evidence. Existing mandatory deep-read and citation/evidence checks remain terminal guards. When a final response fails a guard, the runtime appends a concise guard observation explaining the missing evidence and returns control to the model if budget remains.

The guard must not choose a document, construct a correction query, or invoke a tool. This separates safety policy from planning autonomy.

The current controller remedial path becomes a compatibility mode controlled by an explicit, disabled-by-default setting. If enabled for rollback, traces record that the run was controller-directed. Merely reading a new chunk does not mark a gap resolved; the next model assessment or final evidence check determines sufficiency.

### 7. Separate action budget from reserved terminal synthesis

Configuration will model independent limits rather than a single ambiguous iteration count:

- maximum action rounds, defaulting to the existing value of six,
- maximum total LLM calls,
- maximum total tool calls,
- maximum parallel workers,
- request wall-clock duration,
- repeated-signature threshold,
- one reserved terminal-synthesis call.

The reserved call is not available for more tools. When action capacity is exhausted and qualifying deep-read evidence exists, the runtime calls the model with tools disabled and a grounded synthesis instruction. When no qualifying evidence exists, it emits the localized deterministic insufficiency fallback.

The normal exit remains no tool calls plus answer content plus passing guards. The runtime also hashes each ordered batch as tool name plus canonical JSON arguments. Repeating the same signature without material evidence growth triggers the terminal path.

Alternative considered: use only a 20-round maximum. A larger ceiling does not prevent repeated expensive actions and makes worst-case latency less predictable.

### 8. Treat provider tool-call support and local execution concurrency separately

The model adapter exposes `parallel_tool_calls` capability with `auto`, `on`, and `off` configuration. In supported mode it sends the provider's explicit parallel-tool option. If the provider rejects that option, the adapter retries once without it, caches the compatibility result for the configured provider/model, and annotates the trace.

Multiple calls returned by a provider can still be locally batched even when the explicit request parameter is unavailable. Conversely, an operator can disable local concurrency while retaining multi-call model responses for diagnosis or rollback.

No new concurrency dependency is required; the synchronous runtime can use Python's bounded `concurrent.futures.ThreadPoolExecutor`.

### 9. Stream terminal content only after a safe response discriminator

The model adapter will parse streaming deltas for both content and tool-call arguments. Providers that guarantee disjoint terminal-content and tool-call streams can classify the response on the first substantive delta: tool-call deltas are buffered into an action batch, while content deltas are forwarded as answer tokens.

For providers without that guarantee, content is buffered until the response is known to contain no tool calls, then emitted through the same token event contract. Reserved tools-disabled synthesis can always stream directly. The runtime never exposes provisional answer text that is later discarded because the response also requested tools.

Alternative considered: make a separate decision call before every streamed answer. That adds another model round to the common path and works against the primary latency goal.

The initial timeline `agent_thought` lifecycle item is a presentation of the running model-decision phase; it does not prove that `thinking` was called. Explicit `thinking` tool output uses its own call ID and audit payload so the frontend does not conflate static progress text, provider reasoning content, and a public reflection tool result.

### 10. Measure latency by responsibility

Existing spans will gain attributes for action round, batch size, execution class, worker limit, queue duration, tool duration, batch wall time, model first byte, terminal first token, signature repetition, budget state, provider fallback, and controller-remedial compatibility mode.

Performance acceptance uses deterministic fake-tool tests rather than external model timing. Two independent delayed tools must overlap within a tolerant wall-time bound. Production traces are used to compare model-call count and latency distribution before and after rollout; they are not a hard unit-test threshold.

## Risks / Trade-offs

- [Concurrent access exposes hidden shared state in retrieval services] -> Move debug and mutable request data into tool results before enabling concurrency; keep a serial feature flag until race-focused tests pass.
- [Provider behavior differs across OpenAI-compatible endpoints] -> Capability configuration, one compatible retry, cached fallback, and buffered content for ambiguous streams.
- [LLM emits multiple calls that are logically dependent] -> Prompt forbids same-batch dependencies, tools only receive pre-batch state, and unknown IDs produce structured failures rather than implicit chaining.
- [Parallel calls increase provider or database load] -> Bound workers and total calls, retain per-request scope, and allow local concurrency to be disabled independently.
- [Stable observation order delays visibility of a fast later call] -> Emit truthful lifecycle timestamps while committing model observations in declared order; correctness and reproducibility take priority over cosmetic completion order.
- [Removing automatic remediation can reduce answers for weak prompts] -> Strengthen action-selection instructions, retain guard observations, evaluate retrieval success, and keep the old behavior behind an explicit rollback flag.
- [Tools-disabled synthesis adds one call at the limit] -> Reserve it only for terminal recovery; the normal path still finishes directly when the model returns a valid answer.
- [Streaming auto-tool responses is ambiguous on some providers] -> Stream only after a supported discriminator; otherwise buffer without changing correctness.
- [Model may over-batch redundant searches] -> Enforce call budgets, normalized signature detection, and prompt guidance to select the smallest sufficient independent set.

## Migration Plan

1. Introduce typed tool execution results, state deltas, request-scoped retrieval debug data, and field-specific merge tests while preserving serial execution.
2. Add safety metadata and the batch scheduler behind a disabled local-concurrency flag; verify deterministic messages and domain events.
3. Update prompt policy to first-retrieval-batch grep semantics and model-owned remediation. Add the legacy remedial compatibility flag with its default initially matching current behavior for a short validation window.
4. Run autonomy, evidence-guard, loop, provider, SSE, and controlled-concurrency tests. Validate selected existing chat scenarios against both scheduler modes.
5. Enable multi-call batching, then bounded local concurrency in development. Compare model-round counts, failure rates, first-token latency, and full latency spans.
6. Change the remedial compatibility default to disabled as the target behavior and document the rollback variable.
7. Enable provider-specific parallel tool-call and terminal-streaming capabilities incrementally.

Rollback does not require a data migration. Operators can disable local concurrency, disable the provider parallel option, and re-enable legacy controller remediation independently. The typed result contract remains valid in serial mode.

## Open Questions

- Which configured OpenAI-compatible providers can guarantee that streamed content and streamed tool calls are disjoint enough for early terminal classification?
- Should `thinking` remain a registered public tool after direct action summaries and batch events provide equivalent timeline context, or should it be retained only for explicit audit use?
- What initial wall-clock and total-tool budgets best fit local models versus hosted models? The existing six action rounds should remain the baseline until trace data supports a change.
- Should provider capability fallback be cached only in process memory or persisted by provider/model configuration?
