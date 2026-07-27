## Why

The backend currently has document-processing spans and agent traces, but application logs are not configured as a coherent diagnostic system. When an API request fails, operators need a stable trace ID, a durable log file, and enough request-flow context to find the exact failing component and traceback.

## What Changes

- Add configurable application logging controlled by `LOG_LEVEL`, `LOG_PATH`, and `LOG_FORMAT`.
- Write logs to stdout and, when configured, to a log file such as `log/app.log`.
- Add request trace ID propagation for every FastAPI request using `X-Trace-ID` or `X-Request-ID`.
- Add request middleware that logs request start/end, status code, duration, route, method, client IP, and bounded sanitized request/response summaries.
- Ensure unhandled errors and handler failures record full traceback details with the same trace ID.
- Add lightweight flow logging around critical RAG operations such as upload, parse, query, delete, provider calls, and background batch processing.
- Preserve existing document-processing span trees and agent traces; this change complements them instead of replacing them.

## Capabilities

### New Capabilities

- `observability-request-logging`: Application logging, request trace ID propagation, log file output, custom log formatting, sanitized request/response logging, exception tracebacks, and critical backend flow diagnostics.

### Modified Capabilities

None.

## Impact

- Backend startup and logging initialization in `backend/app/main.py`.
- New backend logging utilities under `backend/app/services/` or a small dedicated logging module.
- FastAPI middleware for request tracing, access logs, and exception logging.
- Selected backend service call sites in `rag_service`, provider wrappers, repositories, and background upload processing.
- Backend configuration examples in `.env.example`, `backend/rag_config.example.yaml`, and README/development docs.
- Tests for log configuration, trace ID propagation, log file writing, formatting, sanitization, and traceback capture.
