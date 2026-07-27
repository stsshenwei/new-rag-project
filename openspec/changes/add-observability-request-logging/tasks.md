## 1. Logging Configuration

- [x] 1.1 Add a backend logging configuration module with idempotent initialization
- [x] 1.2 Parse `LOG_LEVEL` with supported aliases and safe fallback behavior
- [x] 1.3 Configure stdout logging and optional `LOG_PATH` file logging with parent directory creation
- [x] 1.4 Implement `LOG_FORMAT` placeholder rendering for `%d`, `%level`, `%traceId`, `%logger`, and `%msg`
- [x] 1.5 Ensure uvicorn, FastAPI, and application loggers share the configured handlers without duplicate lines

## 2. Trace ID Context

- [x] 2.1 Add context variable helpers for setting, getting, and clearing the active request trace ID
- [x] 2.2 Add a logging filter that injects `traceId` and `trace_id` into every log record
- [x] 2.3 Sanitize incoming trace IDs before putting them into logs
- [x] 2.4 Add tests proving logs outside request context do not fail formatting

## 3. Request Middleware

- [x] 3.1 Add FastAPI middleware that reads `X-Trace-ID`, falls back to `X-Request-ID`, or generates a new trace ID
- [x] 3.2 Return the active trace ID in the `X-Trace-ID` response header
- [x] 3.3 Log request start and end with method, path, status code, duration, client IP, and trace ID
- [x] 3.4 Summarize streaming and multipart responses without buffering full bodies
- [x] 3.5 Add route tests for provided trace ID, generated trace ID, and response header propagation

## 4. Sanitization

- [x] 4.1 Add reusable sanitization for sensitive headers and JSON/text body fields
- [x] 4.2 Bound logged request and response body snippets with a truncation marker
- [x] 4.3 Skip or summarize binary uploads, file downloads, and SSE payloads
- [x] 4.4 Add tests for token, API key, password, authorization, cookie, and large-body redaction

## 5. Exception Logging

- [x] 5.1 Add boundary logging for unhandled request exceptions with full traceback and trace ID
- [x] 5.2 Update key 500-handling routes to log exceptions before raising `HTTPException`
- [x] 5.3 Keep expected 400/404 errors concise without unnecessary traceback noise
- [x] 5.4 Add tests proving a failing request writes traceback details to configured logs

## 6. Critical Flow Logs

- [x] 6.1 Add upload and upload-batch flow logs for create, add-file, confirm, retry, cancel, start, finish, and failure
- [x] 6.2 Add document processing flow logs for parse, chunk, index, multimodal, and postprocess lifecycle events
- [x] 6.3 Add query flow logs for scope resolution, retrieval start/end, candidate counts, and answer generation status
- [x] 6.4 Add delete flow logs for repository deletion, vector deletion, image cleanup, object cleanup, and failures
- [x] 6.5 Add provider boundary logs for LLM, embedding, reranker, parser, OCR, and enrichment calls where wrappers already exist
- [x] 6.6 Ensure background tasks inherit or generate operation trace IDs and log task failures with traceback

## 7. Documentation

- [x] 7.1 Document `LOG_LEVEL`, `LOG_PATH`, and `LOG_FORMAT` in backend environment examples
- [x] 7.2 Add a troubleshooting note explaining how to search `log/app.log` by `X-Trace-ID`
- [x] 7.3 Document what is intentionally not logged for privacy and safety

## 8. Validation

- [x] 8.1 Run backend logging and API route tests
- [x] 8.2 Run a manual smoke test for a successful `/health` request and verify stdout/file logs
- [x] 8.3 Run a manual smoke test for a controlled failing request and verify trace ID plus traceback in `log/app.log`
- [x] 8.4 Verify document-processing span trees and agent trace payloads still work independently of application logs
