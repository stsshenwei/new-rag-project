## ADDED Requirements

### Requirement: Local Langfuse Configuration
The system SHALL support local Langfuse configuration using `LANGFUSE_BASE_URL` as the preferred host/base-url variable while preserving `LANGFUSE_HOST` as a backward-compatible alias.

#### Scenario: Local base URL is configured
- **WHEN** `LANGFUSE_ENABLED=true`, `LANGFUSE_BASE_URL=http://localhost:3001`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` are configured
- **THEN** the backend initializes Langfuse with `http://localhost:3001` as the client host

#### Scenario: Existing host alias is configured
- **WHEN** `LANGFUSE_ENABLED=true`, `LANGFUSE_HOST=http://localhost:3001`, and `LANGFUSE_BASE_URL` is empty
- **THEN** the backend initializes Langfuse with `http://localhost:3001` as the client host

### Requirement: Optional Langfuse Dependency
The system SHALL keep Langfuse optional for runtime availability and SHALL report clear diagnostics when Langfuse is enabled but unavailable.

#### Scenario: Langfuse package missing
- **WHEN** `LANGFUSE_ENABLED=true` but the Python `langfuse` package cannot be imported
- **THEN** the backend continues running local logs, SQLite spans, and trace files while recording a single warning that identifies the missing dependency

#### Scenario: Langfuse credentials missing
- **WHEN** `LANGFUSE_ENABLED=true` but public or secret key is missing
- **THEN** the backend treats Langfuse as not configured and exposes that status without failing startup

### Requirement: Pluggable Observability Sink
The system SHALL isolate Langfuse behind a provider-neutral observability sink so application services do not directly construct Langfuse SDK clients.

#### Scenario: Langfuse is disabled
- **WHEN** Langfuse is disabled or unavailable
- **THEN** application services use a no-op observability sink and continue processing without Langfuse-specific branching in business logic

#### Scenario: Langfuse is enabled
- **WHEN** Langfuse is enabled and configured
- **THEN** the Langfuse sink emits traces, spans, generations, events, flushes, and status through the same observability boundary used by the no-op sink

### Requirement: Processing Trace Export
The system SHALL export document processing attempts to Langfuse as sanitized traces and spans when Langfuse is enabled and configured.

#### Scenario: Document processing succeeds
- **WHEN** a document processing attempt parses, chunks, indexes, and postprocesses successfully
- **THEN** Langfuse receives a trace with child spans for processing stages and metadata that includes document id, knowledge-base scope, local trace directory, and status

#### Scenario: Document processing fails
- **WHEN** a processing stage raises an error
- **THEN** Langfuse receives a failed span with bounded error type/message and local trace correlation metadata

### Requirement: Async Trace Context Propagation
The system SHALL preserve trace context across request-triggered background document processing.

#### Scenario: Upload request starts background processing
- **WHEN** an upload or reparse request creates a processing task
- **THEN** the task metadata includes the current trace id and parent span id where available

#### Scenario: Background processor resumes trace
- **WHEN** a background processor handles a task with trace metadata
- **THEN** processing, parsing, chunking, indexing, multimodal, and postprocess observations attach under the originating request trace

#### Scenario: Background processor has no upstream trace
- **WHEN** a scheduled or legacy background task has no upstream trace metadata
- **THEN** the processor creates a standalone trace for that task without failing the task

### Requirement: Model Generation Export
The system SHALL export model-facing calls as sanitized Langfuse generation observations through wrappers or decorators when Langfuse is enabled and configured.

#### Scenario: Chat generation is emitted
- **WHEN** quick-answer or agent chat invokes a chat model
- **THEN** Langfuse records a chat generation with bounded messages, model metadata, stream state, usage when available, and error status when the call fails

#### Scenario: Embedding generation is emitted
- **WHEN** document indexing or retrieval invokes single or batch embedding
- **THEN** Langfuse records an embedding generation with bounded input previews, batch size, dimensions when available, and approximate usage if the provider returns no usage

#### Scenario: Rerank generation is emitted
- **WHEN** retrieval invokes a rerank model
- **THEN** Langfuse records a rerank generation with query metadata, candidate counts, bounded candidate previews or IDs, score summaries, and approximate usage

### Requirement: Retrieval And Agent Trace Export
The system SHALL export sanitized retrieval, agent runtime, and tool-call trace events to Langfuse when Langfuse is enabled and configured.

#### Scenario: Retrieval debug trace emitted
- **WHEN** a query runs retrieval with debug metadata enabled
- **THEN** Langfuse records retrieval phase spans or events for query understanding, expansion, dense/keyword recall, fusion, rerank/degradation, MMR, duplicate removal, parent recall, and context assembly using bounded metadata

#### Scenario: Agent tool call emitted
- **WHEN** intelligent reasoning mode runs an agent tool
- **THEN** Langfuse records the tool name, bounded sanitized arguments, status, duration, error class, and output summary without exposing hidden reasoning or raw provider payloads

#### Scenario: Tool triggers nested work
- **WHEN** an agent tool triggers retrieval, embedding, rerank, or chat calls
- **THEN** those nested observations attach under the corresponding tool span

### Requirement: Trace Correlation
The system SHALL correlate Langfuse records with local request logs, SQLite spans, tasks, documents, and knowledge-base scope.

#### Scenario: HTTP request triggers processing or chat
- **WHEN** a request has an `X-Trace-ID` and triggers document processing, retrieval, or agent tool execution
- **THEN** Langfuse metadata includes that trace id where available together with relevant document id, task id, span id, workspace id, and knowledge base id

### Requirement: Payload Safety
The system SHALL prevent sensitive or unbounded content from being sent to Langfuse.

#### Scenario: Sensitive values are present
- **WHEN** metadata, prompts, tool arguments, provider outputs, headers, cookies, or errors contain secrets or long content
- **THEN** Langfuse payloads contain redacted or bounded summaries rather than raw sensitive values

### Requirement: Operator Diagnostics
The system SHALL expose or log Langfuse status so operators can verify local connection state.

#### Scenario: Operator checks observability status
- **WHEN** the backend starts or an observability status endpoint is called
- **THEN** the system reports whether Langfuse is enabled, configured, package-available, initialized, failed, and which host/base URL is selected
