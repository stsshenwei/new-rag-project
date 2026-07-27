## ADDED Requirements

### Requirement: Configurable application logging
The backend SHALL configure application logging from environment variables before serving requests.

#### Scenario: Log level is configured
- **WHEN** `LOG_LEVEL` is set to `debug`, `info`, `warn`, `warning`, `error`, `fatal`, or `critical`
- **THEN** backend logging uses the matching severity threshold

#### Scenario: Invalid log level falls back safely
- **WHEN** `LOG_LEVEL` is set to an unsupported value
- **THEN** backend logging falls back to `info` and records a startup warning

#### Scenario: Log file output is enabled
- **WHEN** `LOG_PATH` is set to a writable file path such as `log/app.log`
- **THEN** backend logs are written to both stdout and that file

#### Scenario: Log file output fails safely
- **WHEN** `LOG_PATH` cannot be opened for writing
- **THEN** backend startup continues with stdout logging and records a warning

### Requirement: Custom log format supports trace ID
The backend SHALL support Weknora-style `LOG_FORMAT` placeholders for application logs.

#### Scenario: Custom format is applied
- **WHEN** `LOG_FORMAT` is set to `%d %level %traceId %msg`
- **THEN** each emitted log line uses timestamp, severity, current trace ID, and message in that order

#### Scenario: Default format remains readable
- **WHEN** `LOG_FORMAT` is not set
- **THEN** each emitted log line includes timestamp, severity, trace ID, logger name, and message

#### Scenario: Missing trace ID has placeholder
- **WHEN** code logs outside an active request context
- **THEN** the log record includes a stable empty trace ID placeholder rather than raising a formatting error

### Requirement: Request trace ID propagation
The backend SHALL assign a trace ID to every HTTP request and expose it to logs and clients.

#### Scenario: Existing trace ID is accepted
- **WHEN** a request includes `X-Trace-ID`
- **THEN** the backend uses that value as the active request trace ID after sanitization

#### Scenario: Request ID fallback is accepted
- **WHEN** a request does not include `X-Trace-ID` but includes `X-Request-ID`
- **THEN** the backend uses `X-Request-ID` as the active request trace ID after sanitization

#### Scenario: Missing trace ID is generated
- **WHEN** a request includes neither `X-Trace-ID` nor `X-Request-ID`
- **THEN** the backend generates a new trace ID for that request

#### Scenario: Trace ID is returned
- **WHEN** the backend responds to a request
- **THEN** the response includes `X-Trace-ID` with the active request trace ID

### Requirement: Request lifecycle logging
The backend SHALL log a bounded request lifecycle record for each HTTP request.

#### Scenario: Successful request is logged
- **WHEN** a request completes successfully
- **THEN** logs include method, path, status code, duration, client IP, and trace ID

#### Scenario: Failed request is logged
- **WHEN** a request returns a 5xx response
- **THEN** logs include method, path, status code, duration, client IP, trace ID, exception type, exception message, and traceback when available

#### Scenario: Streaming response is summarized
- **WHEN** a request returns an SSE or streaming response
- **THEN** request lifecycle logs summarize the response without buffering or logging the full stream body

#### Scenario: Upload body is summarized
- **WHEN** a request uploads a binary or multipart file
- **THEN** request lifecycle logs summarize content type and size metadata without logging raw file bytes

### Requirement: Sensitive log data is redacted
The backend SHALL redact sensitive fields from request logs, response logs, and exception context.

#### Scenario: Sensitive headers are redacted
- **WHEN** request or response headers contain authorization, cookie, set-cookie, token, api key, secret, or password values
- **THEN** the logged value is replaced with a redacted placeholder

#### Scenario: Sensitive JSON fields are redacted
- **WHEN** a logged JSON body contains fields such as `password`, `token`, `api_key`, `secret`, `authorization`, or `client_secret`
- **THEN** those field values are replaced with a redacted placeholder

#### Scenario: Logged bodies are bounded
- **WHEN** a text or JSON request/response body exceeds the configured log body limit
- **THEN** logs include only the bounded prefix and a truncation marker

### Requirement: Critical backend flows are traceable in logs
The backend SHALL log key RAG operation flow stages with the active trace ID or a generated operation trace ID.

#### Scenario: Document upload flow is logged
- **WHEN** a document upload or upload batch confirm operation starts and finishes
- **THEN** logs include workspace ID, knowledge base ID, batch ID or file ID when available, operation status, duration, and trace ID

#### Scenario: Document processing flow is logged
- **WHEN** document parsing, chunking, indexing, multimodal processing, or postprocessing starts and finishes
- **THEN** logs include document ID, stage name, status, duration, and trace ID

#### Scenario: Query flow is logged
- **WHEN** `/rag/query` or `/chat/stream` performs retrieval and answer generation
- **THEN** logs include requested scope, selected document IDs when provided, retrieval mode, candidate counts when available, status, duration, and trace ID

#### Scenario: Delete flow is logged
- **WHEN** a document delete request executes repository, vector store, image, or object storage cleanup
- **THEN** logs include the component name, document ID, scope, status, duration, and trace ID

#### Scenario: Background task failures are logged
- **WHEN** a background upload or processing task fails
- **THEN** logs include operation identifiers, exception type, exception message, traceback, and the inherited or generated trace ID

### Requirement: Existing trace systems are preserved
The backend SHALL keep document-processing span trees and agent traces as separate user-facing trace mechanisms.

#### Scenario: Document span tree still records processing
- **WHEN** a document is parsed and indexed
- **THEN** `knowledge_processing_spans` continues to record the processing stages independently of application log files

#### Scenario: Agent trace payloads remain unchanged
- **WHEN** chat or RAG APIs emit agent trace payloads
- **THEN** those payloads remain safe public trace summaries and are not replaced by application logs
