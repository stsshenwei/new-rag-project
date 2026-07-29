# Verification

## Runtime Span Comparison

The before sample comes from the existing `agent_runtime_spans` reviewed during design. Completed production runs ranged from about 14 to 99 seconds. Model rounds were about 6 to 22 seconds each, grep was about one second, local full-content reads were usually tens of milliseconds, and semantic retrieval could take about ten seconds. Those traces commonly serialized search, read, reflection, and corrective retrieval across additional model turns.

The after sample is a deterministic local scripted-model run on 2026-07-28. It represents the expected common control flow without external provider latency:

| Field | Before sample | After controlled sample |
| --- | --- | --- |
| Model calls | Multiple serialized decision/remediation turns | 3 |
| Action batches | Commonly one action per round | `[2, 2]` |
| Path | Search, later semantic/search, later reads, final | grep + semantic; two reads; terminal synthesis |
| First-token ordering | Existing references-before-token contract | sources event index 25, first token index 28 |
| Total latency | About 14-99 seconds | 12 ms with fake model and local fake tools |
| Provider fallback | Not consistently recorded | `false` |
| Terminal synthesis | Hard-coded max-round fallback | tools-disabled synthesis used |

The controlled total latency is not a production forecast because it excludes network model and real retrieval latency. Its purpose is to prove call count, batching, event ordering, and span fields deterministically.

## Scheduler Timing

The deterministic scheduler tests use two parallel-safe tools delayed by 180 ms and 40 ms. Concurrent execution must finish below 300 ms and preserve declared result order; the equivalent serial execution returns identical tool outputs, evidence IDs, and ordering. Separate serial and exclusive barriers are verified not to overlap.

## SSE And UI

The local `/chat/stream` route smoke uses one reasoning batch with `grep_chunks` and `knowledge_search`, out-of-order physical completion metadata, source references, two answer-token events, `agent_complete`, and final `[DONE]`. The frontend reducer test verifies both calls complete by call ID, remain in declared order, and leave no running spinner. Existing scoped route and feedback tests verify knowledge-base isolation and answer-feedback persistence.

## Remaining Bottlenecks

- Hosted or local model latency remains the dominant cost per ReAct round.
- Semantic retrieval can remain a material cost even when overlapped with grep.
- Serial and exclusive tools intentionally form barriers.
- Providers in compatibility fallback mode do not receive the explicit parallel-tool option.
- `auto` terminal streaming buffers ambiguous provider responses until tool-call absence is known.
