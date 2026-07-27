## Context

The project already records document processing evidence in three places: request-scoped logs, SQLite `knowledge_processing_spans`, and local trace files under `PROCESSING_TRACE_DIR`. `ProcessingTraceRecorder` also has a partial Langfuse integration, but it currently reads only `LANGFUSE_HOST`, depends on an undeclared optional `langfuse` package, and covers mainly production document processing spans.

The user has a local Langfuse server running at `LANGFUSE_BASE_URL="http://localhost:3001"`. The project should accept that configuration directly and make Langfuse useful for operations without making Langfuse a hard runtime dependency.

## Goals / Non-Goals

**Goals:**

- Support local Langfuse setup with `LANGFUSE_BASE_URL=http://localhost:3001` while preserving the existing `LANGFUSE_HOST` env name.
- Provide clear enabled/configured/package/connection diagnostics.
- Emit sanitized traces for document processing, retrieval, agent runtime, and tool calls.
- Correlate Langfuse traces with local `X-Trace-ID`, SQLite span IDs, document IDs, task IDs, knowledge-base scope, and local trace directories.
- Keep all local observability paths working when Langfuse is disabled, unreachable, or missing credentials.
- Document the exact local setup steps.

**Non-Goals:**

- Do not make Langfuse required for backend startup.
- Do not store hidden reasoning, raw prompts, secrets, cookies, provider raw payloads, full uploaded files, or unbounded document chunks in Langfuse.
- Do not replace SQLite span trees, local trace artifacts, or request log files.
- Do not add remote SaaS-specific setup beyond generic host/key configuration.

## Decisions

### Decision: Add a pluggable observability sink boundary

Create a provider-neutral observability boundary such as `ObservabilitySink` / `TraceSink`, with at least a `NoopObservabilitySink` and a `LangfuseObservabilitySink`. The Langfuse sink owns env parsing, lazy client construction, failure caching, flush behavior, status reporting, and safe trace/span/generation helpers. `ProcessingTraceRecorder`, retrieval code, model clients, and agent runtime should call this boundary rather than each constructing a Langfuse client.

Alternative considered: keep Langfuse logic embedded only in `processing_trace.py`. That would keep the change smaller but would spread duplicate initialization if retrieval and agent traces are added later.

Alternative considered: route all model calls through a Langfuse/OpenAI proxy. This would capture some LLM calls, but it would not naturally capture document parsing, chunking, retrieval fusion, tool execution, local span IDs, or background task correlation. A pluggable sink is a better fit for this codebase because local SQLite spans and request logs remain first-class.

### Decision: Use decorators for model-level generations

Mirror Weknora's pattern by wrapping model-facing services where practical. Chat, embedding, rerank, and later VLM/ASR-capable services should emit Langfuse `generation` observations through the shared sink. Higher-level document processing, retrieval, and agent/tool workflows should emit `span` observations. This keeps trace trees readable:

```text
request trace
  processing/retrieval/agent span
    chat/embedding/rerank generation
    tool span
      nested retrieval/model generation
```

### Decision: Propagate trace context across async processing

Document uploads and reprocessing requests are asynchronous in practice. The HTTP/request side should create or reuse a trace context, persist/pass the trace id and parent span id into the processing task metadata, and the background processor should resume that trace when it parses, chunks, indexes, runs multimodal work, and postprocesses. If a background task has no upstream request trace, it should create a standalone trace rather than dropping observability.

### Decision: Treat `LANGFUSE_BASE_URL` as the preferred local alias

Configuration resolution should use:

```text
LANGFUSE_BASE_URL -> LANGFUSE_HOST -> default empty
```

The Langfuse Python SDK calls this value `host`, but many local Docker examples and users naturally call it a base URL. Supporting both removes friction and preserves backward compatibility.

### Decision: Fail open, but diagnose clearly

If `LANGFUSE_ENABLED=true` but keys are missing, package import fails, or the server is unreachable, the backend should continue using logs, SQLite spans, and local files. It should emit one concise warning and expose status through a health/debug route or startup status object.

Alternative considered: fail startup when Langfuse is enabled but unavailable. That would catch misconfiguration early, but it would make an observability sink a production availability dependency.

### Decision: Sanitize and bound all Langfuse payloads

Langfuse metadata should include IDs, status, counts, durations, stage names, tool names, bounded argument summaries, selected KB scope, retrieval counters, and safe error classes/messages. It must not include secrets, raw Authorization headers, cookies, long document content, full provider payloads, or hidden reasoning.

### Decision: Keep local trace as source of truth

SQLite `knowledge_processing_spans` remains the authoritative tree for the frontend Trace drawer. Langfuse is a secondary sink used for cross-request and cross-component observability. Local `trace.json`, `report.md`, `parsed.md`, `chunks.jsonl`, and `chunks_preview.md` remain manual debugging artifacts.

## Risks / Trade-offs

- [Risk] Langfuse SDK API versions may differ. -> Mitigation: wrap client calls behind compatibility helpers that support `trace/span/end/flush` variants and unit-test with fake clients.
- [Risk] Observability calls could slow processing. -> Mitigation: lazy initialize, bound payloads, catch exceptions, and flush only at attempt/request boundaries.
- [Risk] Sensitive data could leak to Langfuse. -> Mitigation: reuse existing redaction/sanitization helpers and add tests for secrets, raw prompts, hidden reasoning, cookies, and long content.
- [Risk] Local Langfuse URL naming can confuse users. -> Mitigation: document `LANGFUSE_BASE_URL` as preferred local config and keep `LANGFUSE_HOST` as compatible alias.

## Migration Plan

1. Add or confirm the `langfuse` dependency in `backend/requirements.txt`.
2. Add env parsing for `LANGFUSE_BASE_URL`, `LANGFUSE_HOST`, `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`.
3. Introduce the pluggable observability sink boundary and migrate `ProcessingTraceRecorder` to use it.
4. Add async trace context propagation between upload/reparse requests and background processing.
5. Add model-client decorators for chat, embedding, and rerank generation observations.
6. Add retrieval and agent/tool trace emission through the shared boundary.
7. Add diagnostics endpoint or health payload field for Langfuse status.
8. Update `.env.example`, README, and development docs with local Langfuse setup.

Rollback is configuration-only: set `LANGFUSE_ENABLED=false`. The local logs, SQLite span tree, and local trace files continue to work.

## Open Questions

- Should Langfuse status be exposed through `/health`, a new `/observability/status`, or both?
- Should quick-answer LLM calls become Langfuse generation spans now, or should this change limit itself to processing/retrieval/agent/tool spans?
- Should local development enable Langfuse by default when keys are present, or require explicit `LANGFUSE_ENABLED=true`?
- Should the first implementation add an internal event bus for observability, or keep direct `ObservabilitySink` calls at existing service boundaries?
