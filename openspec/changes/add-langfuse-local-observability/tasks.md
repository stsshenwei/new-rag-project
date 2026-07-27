## 1. Configuration And Dependency

- [x] 1.1 Add or confirm the backend `langfuse` dependency and document optional runtime behavior when the package is unavailable.
- [x] 1.2 Add configuration parsing for `LANGFUSE_BASE_URL` with `LANGFUSE_HOST` fallback, `LANGFUSE_ENABLED`, public key, secret key, and safe defaults.
- [x] 1.3 Update `.env.example`, README, and development docs with local Langfuse setup using `LANGFUSE_BASE_URL=http://localhost:3001`.

## 2. Shared Langfuse Observability Boundary

- [x] 2.1 Define a provider-neutral observability sink interface for trace, span, generation, event, flush, and status operations.
- [x] 2.2 Implement a no-op sink that is used when Langfuse is disabled, missing credentials, missing package, or failed.
- [x] 2.3 Implement a Langfuse sink for lazy client initialization, failure caching, status reporting, trace/span/generation helpers, and flush.
- [x] 2.4 Ensure application services depend on the sink boundary rather than importing or constructing Langfuse SDK clients directly.
- [x] 2.5 Add sanitization and size bounding for Langfuse inputs, outputs, metadata, headers, tool arguments, provider results, errors, and document snippets.
- [x] 2.6 Add unit tests for env alias precedence, missing keys, missing package behavior, failed initialization, flush safety, no-op fallback, and sanitized payloads.

## 3. Processing Trace Integration

- [x] 3.1 Migrate `ProcessingTraceRecorder` to use the shared Langfuse service while preserving SQLite span tree and local trace file behavior.
- [x] 3.2 Emit processing root/stage/subspan/generation spans with document id, scope, task id when available, trace id, local trace directory, status, duration, and bounded error fields.
- [x] 3.3 Persist or pass upstream trace context from upload/reparse requests into background processing metadata so worker-side processing can resume the same trace tree.
- [x] 3.4 Create standalone processing traces for background jobs that have no upstream request trace.
- [x] 3.5 Add tests for successful processing trace export, failed stage export, disabled Langfuse fallback, async trace context propagation, standalone background traces, and local trace continuity.

## 4. Model Generation Decorators

- [x] 4.1 Add wrapper/decorator instrumentation for quick-answer chat calls so they emit `chat.completion` or `chat.completion.stream` generation observations.
- [x] 4.2 Add wrapper/decorator instrumentation for embedding calls so single and batch embedding emit bounded generation observations and approximate usage when providers do not return token usage.
- [x] 4.3 Add wrapper/decorator instrumentation for rerank calls so rerank emits bounded generation observations with candidate counts, preview IDs, score summaries, and approximate usage.
- [x] 4.4 Ensure generation observations attach under the current request, processing, retrieval, or agent span through propagated context.
- [x] 4.5 Add tests for chat, streaming chat, embedding, batch embedding, and rerank generation payloads, including error and disabled-sink paths.

## 5. Retrieval And Chat Correlation

- [x] 5.1 Propagate request trace id into retrieval and chat paths where available.
- [x] 5.2 Emit retrieval spans/events for query understanding, expansion, dense/keyword recall, fusion, rerank/degradation, MMR, duplicate removal, parent recall, and context assembly using bounded debug metadata.
- [x] 5.3 Ensure retrieval spans include safe counters, selected knowledge-base scope, document/chunk IDs, score summaries, and degradation reasons without full chunk bodies.
- [x] 5.4 Add tests that retrieval Langfuse payloads include correlation ids and do not include full raw prompts, secrets, or unbounded chunk content.

## 6. Agent Runtime And Tool Integration

- [x] 6.1 Emit agent runtime Langfuse traces/spans for reasoning mode start, rounds, deep-read enforcement, answer return, and failures.
- [x] 6.2 Emit tool-call spans with tool name, bounded sanitized arguments, status, duration, error class, output summary, and source chunk ids when applicable.
- [x] 6.3 Attach nested retrieval/model observations triggered by tools under the corresponding `agent.tool.<name>` span.
- [x] 6.4 Add tests for successful tool spans, unavailable tool spans, failing tool spans, nested tool observations, and hidden-reasoning redaction.

## 7. Operator Diagnostics

- [x] 7.1 Add a startup log entry and health/debug status payload that reports Langfuse enabled, configured, package availability, selected host/base URL, initialized, and failed state.
- [x] 7.2 Add a bounded connection/status check that does not block startup or fail health when Langfuse is unreachable.
- [x] 7.3 Add tests for diagnostics with disabled, configured, missing-key, missing-package, unreachable-host, and failed-client states.

## 8. Validation

- [x] 8.1 Run targeted backend tests for Langfuse config, sink boundary, model decorators, processing trace, retrieval, agent runtime, tool tracing, request logging, and health diagnostics.
- [ ] 8.2 Run a local manual smoke test against `LANGFUSE_BASE_URL=http://localhost:3001` and document expected trace names/metadata in validation notes.
- [x] 8.3 Verify existing local observability still works with `LANGFUSE_ENABLED=false`.
- [ ] 8.4 Verify upload-to-background-processing traces appear as one connected tree when credentials and local Langfuse are configured.
