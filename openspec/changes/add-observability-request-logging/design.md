## Context

The backend already has several trace-like mechanisms:

- document processing spans in SQLite through `knowledge_processing_spans`
- file artifacts such as `trace.json`, `report.md`, and `chunks_preview.md`
- agent trace payloads for chat and retrieval workflows
- scattered `logging.getLogger(__name__)` calls across services

What is missing is request-level observability. A user can see an HTTP 500, but the backend does not guarantee a shared trace ID across middleware, route handlers, service logs, background callbacks, provider calls, and exception tracebacks. Logs also do not have a project-owned configuration path for stdout + file output, custom formatting, or bounded sanitized request/response records.

Weknora provides a useful pattern: configure logging from env, attach a request ID in middleware, inject it into logging context, log request input/output safely, and preserve full traceback details for failures. This project should implement the same idea with Python-native `logging`, `contextvars`, and FastAPI middleware rather than adding a large logging framework.

## Goals / Non-Goals

**Goals:**

- Configure backend logging from `LOG_LEVEL`, `LOG_PATH`, and `LOG_FORMAT`.
- Write logs to stdout and, when `LOG_PATH` is set, to the configured file.
- Generate or accept a request trace ID for every HTTP request.
- Return the trace ID in a response header so users can report it.
- Make every Python log record automatically include the current trace ID.
- Log request start/end with method, path, status, duration, client IP, and bounded sanitized request/response summaries.
- Record full exception tracebacks for 500s and background task failures.
- Add flow logs for critical RAG operations without duplicating document span storage.
- Avoid logging secrets, bearer tokens, API keys, uploaded binary content, or full large responses.

**Non-Goals:**

- Do not replace document-processing span trees or Langfuse integration.
- Do not add a new external observability service.
- Do not persist every request into SQLite.
- Do not expose raw prompts, hidden reasoning, private memory content, or provider secrets.
- Do not change API response bodies except for safe trace ID metadata where explicitly specified.

## Decisions

### Decision 1: Use Python logging with a small project-owned configuration layer

Add a small backend logging module responsible for:

- parsing `LOG_LEVEL`
- resolving `LOG_PATH`
- configuring root and uvicorn loggers
- adding stdout and optional file handlers
- installing a formatter that understands `LOG_FORMAT`
- attaching a filter that injects `traceId`

Supported levels:

```text
debug, info, warn, warning, error, fatal, critical
```

Invalid levels should fall back to `info` and emit a warning.

Rationale: The codebase already uses Python logging. A local configuration module improves behavior without changing call sites to a new logger API.

Alternative considered: Add `loguru` or `structlog`. That would be pleasant, but it is unnecessary for the current need and would force a broader logging migration.

### Decision 2: Treat trace ID as request-scoped context

Use `contextvars.ContextVar` to store the active trace ID. The request middleware should:

1. read `X-Trace-ID`
2. otherwise read `X-Request-ID`
3. otherwise generate a UUID
4. sanitize and bind it to context
5. return it as `X-Trace-ID`

The logging filter should write the value into `record.traceId` and `record.trace_id` so both custom and conventional formatters can use it.

Rationale: `contextvars` works naturally with async FastAPI request handling and keeps existing service code free from manual trace ID plumbing.

Alternative considered: Pass trace ID explicitly through service method signatures. This is more explicit but invasive and easy to miss.

### Decision 3: Custom format supports Weknora-style placeholders

`LOG_FORMAT` should support these placeholders:

```text
%d        timestamp with milliseconds
%level    uppercase level
%traceId  current trace ID or "-"
%logger   logger name
%msg      rendered message plus structured extras when available
```

Default format should be readable even without `LOG_FORMAT`, for example:

```text
2026-07-19 10:30:45.123 INFO trace=- app.main | Backend started
```

The user's example should work:

```bash
LOG_FORMAT="%d %level %traceId %msg"
```

Rationale: This preserves the requested interface while keeping implementation small.

Alternative considered: Require Python `%()` formatter syntax. That is native, but it does not match the user-facing Weknora-like configuration.

### Decision 4: Request logging is bounded and sanitized

The middleware should log a compact request lifecycle:

```text
request.start method=DELETE path=/rag/documents/... traceId=...
request.end method=DELETE path=/rag/documents/... status=500 duration_ms=... traceId=...
```

For JSON/text request and response bodies, log at most a configurable small limit. Binary uploads and SSE streams should be summarized rather than copied. Sensitive fields and headers must be redacted:

```text
authorization, cookie, set-cookie, token, api_key, api-key, secret, password, bearer
```

Rationale: The goal is diagnosis, not data capture. Enterprise logs must help debug without becoming a secret leak.

Alternative considered: Log full bodies in debug mode. Rejected because prompts, documents, and API keys can be sensitive even in local debug logs.

### Decision 5: Exceptions are logged once at the boundary with full traceback

Unhandled errors and explicit 500 conversions should log full tracebacks at the route/middleware boundary with the current trace ID. Existing service-level `logger.exception` calls can remain, but route handlers should stop swallowing useful tracebacks without logging.

For HTTP errors intentionally returned as 400/404, logs should be warning or info level and not include stack traces unless the exception is unexpected.

Rationale: Duplicate tracebacks create noise, but missing tracebacks block diagnosis. Boundary logging gives one authoritative failure record per request.

Alternative considered: Log exceptions only in each service. That depends on every call site being diligent and misses framework-level failures.

### Decision 6: Critical flow logging is explicit but lightweight

Add targeted logs around:

- upload batch creation, file add, confirm, retry, cancel
- document parse/ingest lifecycle
- RAG query scope resolution and retrieval start/end
- delete document repository, vector store, image/object cleanup
- external provider calls for LLM, embedding, reranker, parser, OCR, and enrichment
- background batch worker start/end/failure

These logs should include identifiers such as workspace id, knowledge base id, doc id, batch id, file id, provider name, status, duration, and error class when available.

Rationale: When a request crosses multiple services, lifecycle logs show where the failure occurred before reading a stack trace.

Alternative considered: Add a generic span system for every function. That overlaps with existing document spans and would add too much instrumentation.

## Risks / Trade-offs

- [Risk] Logging bodies can leak secrets or document content. -> Mitigation: default to compact metadata, redact sensitive fields, skip binary/SSE content, and cap text length.
- [Risk] Duplicate log handlers can produce repeated lines during `uvicorn --reload`. -> Mitigation: make logging initialization idempotent and replace only project-managed handlers.
- [Risk] File logging can fail because the directory does not exist or is not writable. -> Mitigation: create parent directories when possible, fall back to stdout, and log a startup warning.
- [Risk] Context variables may not propagate into background tasks or worker threads. -> Mitigation: pass trace IDs explicitly into background task entry points where continuity matters and create new operation trace IDs otherwise.
- [Risk] Excess debug logging may slow large upload flows. -> Mitigation: bound body sizes and keep detailed flow logs mostly metadata-based.

## Migration Plan

1. Add logging configuration with stdout behavior equivalent to today when `LOG_PATH` is unset.
2. Add middleware and response header support.
3. Update route-level exception logging for key endpoints.
4. Add targeted flow logs in RAG service and provider boundaries.
5. Document the new env variables and local troubleshooting workflow.
6. Validate with tests and one manual delete/upload/query failure smoke test.

Rollback is simple: unset `LOG_PATH`, set `LOG_LEVEL=info`, and remove the middleware/config initialization if it causes startup issues.

## Open Questions

- Should the frontend display `X-Trace-ID` in error toasts, or is browser devtools/header inspection enough for the first implementation?
- Should request/response body logging be controlled by a separate `LOG_HTTP_BODY_ENABLED` flag?
- Should background upload files inherit the confirm request trace ID or each file get a child operation trace ID?
