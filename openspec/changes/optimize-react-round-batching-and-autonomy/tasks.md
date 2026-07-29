## 1. Baseline and Runtime Contracts

- [x] 1.1 Add focused characterization tests for the current multi-tool response parsing, grep-first guard, deep-read guard, remedial retrieval, terminal answer, max-iteration fallback, domain-event ordering, and SSE adaptation.
- [x] 1.2 Add typed runtime models for action batches, stable call indexes, execution safety classes, tool execution results, structured tool errors, request-scoped debug data, and state deltas.
- [x] 1.3 Extend tool registration so every tool declares `parallel_safe`, `serial`, or `exclusive`, with a conservative default for unclassified tools.
- [x] 1.4 Add configuration models and environment parsing for action-round, LLM-call, tool-call, wall-clock, worker, repeated-signature, local-concurrency, provider-parallel, terminal-streaming, and legacy-remediation controls.

## 2. Race-Free Tool State

- [x] 2.1 Refactor `grep_chunks` to return candidate evidence, debug metadata, counters, and state deltas without mutating shared runtime state.
- [x] 2.2 Refactor `knowledge_search` to return request-scoped retrieval debug metadata and state deltas without using a shared `_last_retrieval_debug` scratch value.
- [x] 2.3 Refactor `list_knowledge_chunks` and `get_document_info` to return deep-read state deltas without mutating shared state.
- [x] 2.4 Refactor `thinking` into a bounded public audit result and returned state delta, and keep `todo_write` on serial replacement semantics.
- [x] 2.5 Implement explicit state-delta reducers for stable ordered candidate unions, deep-read unions, monotonic flags, counters, audit summaries, and serial replacement fields.
- [x] 2.6 Add unit tests proving that concurrent retrieval results retain separate debug data and merge deterministically when candidate IDs overlap.

## 3. Action Batch Validation and Scheduling

- [x] 3.1 Change each ReAct iteration to construct and validate one complete ordered action batch before executing any call.
- [x] 3.2 Remove `_requires_grep_first` lexical intent routing and enforce grep-first only at the first LLM-selected knowledge-base retrieval batch, which can also contain independent semantic or graph calls.
- [x] 3.3 Implement execution segmentation with barriers for serial and exclusive tools and bounded `ThreadPoolExecutor` overlap for contiguous parallel-safe calls.
- [x] 3.4 Ensure workers receive immutable request context and pre-batch state snapshots and cannot emit directly to the shared event bus.
- [x] 3.5 Collect successes, structured failures, state deltas, and timings from all scheduled calls, then commit model tool messages and state changes in original call order.
- [x] 3.6 Isolate ordinary independent-call failures while stopping remaining work for authorization, request-scope, cancellation, or global-budget failures.
- [x] 3.7 Preserve safe serial execution when local concurrency is disabled while retaining one-batch/one-model-round semantics.

## 4. Prompted Autonomy and Evidence Guards

- [x] 4.1 Rewrite the reasoning prompt and runtime terminology so the ReAct Think phase is the tool-enabled LLM inference, the first response may directly select retrieval, and the optional `thinking` tool is never a prerequisite for another tool.
- [x] 4.2 State in the prompt that synonyms, aliases, translations, abbreviations, model fragments, and equivalent parameter expressions belong directly in request-local tool arguments rather than a predefined dictionary.
- [x] 4.3 Remove prompt wording that forces semantic search into a later round after grep, while preserving first-retrieval-batch grep and mandatory deep-read requirements.
- [x] 4.4 Make standalone `thinking` optional and instruct the model to call retrieval directly or co-issue a concise audit summary with independent corrective actions.
- [x] 4.5 Disable controller-selected remedial search and read on the default path; expose the current behavior only through the explicit compatibility setting and trace its use.
- [x] 4.6 Change terminal guard failures into concise model observations that identify the missing evidence condition without selecting a query, tool, document, or chunk.
- [x] 4.7 Add scripted-model tests showing a conversational direct answer without forced grep, a grep-plus-semantic first batch, a later model-selected deep read, an evidence-driven retry with a new alias, and a direct final answer without a forced thinking round.

## 5. Budgets, Loop Detection, and Terminal Synthesis

- [x] 5.1 Track action rounds, total LLM calls, total proposed and executed tool calls, elapsed wall time, and remaining reserved synthesis capacity in request state.
- [x] 5.2 Enforce budgets before model and batch scheduling and produce stable machine-readable stop reasons for every exhausted limit.
- [x] 5.3 Canonicalize ordered tool names and JSON arguments into action signatures and detect repeated signatures only when material evidence state has not grown.
- [x] 5.4 Replace the max-iteration hard-coded answer path with one tools-disabled grounded synthesis call when qualifying deep-read evidence exists.
- [x] 5.5 Preserve a localized deterministic evidence-insufficient fallback when no qualifying evidence exists or terminal synthesis fails.
- [x] 5.6 Add tests for normal terminal answers, repeated-action termination, partial batch budget rejection, wall-clock termination, evidence-backed reserved synthesis, and no-evidence fallback.

## 6. Provider Adaptation and Answer Streaming

- [x] 6.1 Add provider/model capability resolution for explicit parallel tool calls and terminal stream discrimination using `auto`, `on`, and `off` modes.
- [x] 6.2 Send the provider parallel-tool parameter only when enabled, retry once without it on a recognized unsupported-parameter response, and cache and trace the compatibility fallback.
- [x] 6.3 Parse streamed tool-call deltas into an action batch without leaking provisional content or malformed partial arguments into model history.
- [x] 6.4 Stream normal terminal content after a safe provider response discriminator and buffer ambiguous provider responses until no tool calls are confirmed.
- [x] 6.5 Stream the reserved tools-disabled synthesis directly through existing answer-token events and keep the final event last.
- [x] 6.6 Add adapter tests for supported parallel calls, rejected-option retry, compatibility caching, streamed multi-call assembly, safe content buffering, and streamed terminal synthesis.

## 7. Events, Timeline, and Observability

- [x] 7.1 Add stable batch ID, call ID, original index, execution class, and round metadata to internal tool lifecycle events without changing required public event names.
- [x] 7.2 Emit tool starts in declared order, retain truthful completion timestamps, and emit round completion only after every scheduled call reaches a terminal state.
- [x] 7.3 Record action-round duration, model latency, model first byte, tool queue and execution duration, batch wall time, terminal first token, worker count, budgets, signature stops, and fallback modes in runtime spans.
- [x] 7.4 Distinguish the running LLM decision lifecycle event, provider reasoning stream, and explicit `thinking` tool result by event source and call identity without exposing private reasoning.
- [x] 7.5 Update the frontend timeline reducer if necessary so batched child completion always completes parent reasoning steps and no completed step retains a spinner.
- [x] 7.6 Add backend event-contract and frontend reducer tests for out-of-order physical completion, mixed success and failure, streamed answer tokens, final ordering, and duplicate-event resistance.

## 8. Performance, Integration, and Documentation

- [x] 8.1 Add deterministic fake-tool timing tests proving two parallel-safe delayed calls overlap within tolerance while serial and exclusive barriers do not overlap.
- [x] 8.2 Add an end-to-end scripted-model test whose typical path is one grep-plus-semantic batch, one multi-read batch, and one final answer, with exactly three model turns and no controller-generated retrieval.
- [x] 8.3 Run the relevant backend unit and integration suites and frontend tests, and compare serial versus concurrent scheduler results for answer, evidence, source, and event equivalence.
- [x] 8.4 Update `docs/design-docs/backend-rag-pipeline.md`, `docs/ARCHITECTURE.md`, and `docs/DEVELOPMENT.md` with batch semantics, autonomy boundaries, configuration, trace fields, and rollback controls.
- [x] 8.5 Perform a local SSE smoke test for a multi-tool reasoning query and verify answer streaming, source display, completed timeline icons, scope isolation, and feedback flow.
- [x] 8.6 Capture before-and-after runtime spans for representative queries and document model-call count, batch size, first-token latency, total latency, fallback use, and any remaining serial bottleneck.
