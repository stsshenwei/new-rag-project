## Why

The current reasoning runtime supports a ReAct loop, but prompt wording and controller-side remedial retrieval often turn it into a serial pipeline: one model round selects one action, tools in the same response execute sequentially, and a `thinking` result can trigger hard-coded follow-up searches. Production traces show that repeated LLM round trips dominate end-to-end latency, with completed runs ranging from roughly 14 to 99 seconds, so the runtime needs to preserve LLM autonomy while batching independent work and retaining evidence safety.

## What Changes

- Let the reasoning model decide, on every round, whether retrieval is needed and whether to answer or call one or more available tools; runtime code will enforce safety and budgets but will not use lexical heuristics to pre-plan the first action or prescribe a fixed retrieval sequence.
- Define the ReAct `Think` phase as the tool-enabled LLM inference itself: the first model response can directly emit `grep_chunks` with request-local synonyms. The optional `thinking` tool remains a public audit/reflection action and is never a prerequisite for retrieval.
- Redefine grep-first as a first-retrieval-batch requirement, allowing the model to issue `grep_chunks` together with independent semantic or graph retrieval calls in the same round.
- Execute independent, parallel-safe tool calls from one model response as a bounded batch, while preserving serial or exclusive execution for stateful and dependent tools.
- Replace concurrent mutation of shared runtime state with request-scoped tool results and deterministic, controller-owned state merging.
- Remove controller-triggered remedial search and deep-read behavior from the default path; gaps and corrected queries become observations that the model may act on in its next tool selection.
- Keep mandatory full-content reading and evidence sufficiency checks as answer guards without making those guards choose the next tool or query.
- Improve termination with repeated tool-call signature detection, explicit time/call budgets, and a reserved tools-disabled final synthesis when the action-round limit is reached.
- Stream terminal answer synthesis when the configured provider supports it, and add round, batch, tool wait, model latency, and first-token measurements.
- Add provider capability fallback so unsupported parallel tool-call parameters or concurrent execution degrade safely to compatible behavior.

## Capabilities

### New Capabilities

- `react-round-batching-and-autonomy`: Defines model-owned ReAct action selection, first-batch grep semantics, safe same-round tool batching, evidence guards, termination and budget behavior, provider fallback, and runtime observability.

### Modified Capabilities

None. Existing related capabilities have not yet been archived into the main specification set; compatibility with their active changes is addressed in this change's design and tasks.

## Impact

- Backend runtime orchestration in `backend/app/services/agent_runtime.py`.
- Tool contracts and state ownership in `backend/app/services/agent_runtime_tools.py` and related runtime models.
- Reasoning prompt policy in `backend/config/prompt_templates/agent_system_prompt.yaml`.
- Runtime settings exposed through backend environment/config construction.
- Agent domain events, SSE adaptation, and latency span attributes, while preserving existing public event names and answer/source ordering.
- Unit and integration tests for tool batching, deterministic state merging, autonomy, deep-read guards, provider fallback, loop termination, and streaming.
- Backend retrieval and runtime design documentation; no knowledge ingestion, vector schema, or public HTTP route change is required.
