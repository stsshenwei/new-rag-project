## ADDED Requirements

### Requirement: Database Span Tree
The system SHALL record document processing trace as a database span tree with root, stage, subspan, and generation nodes.

#### Scenario: Processing attempt opens stage tree
- **WHEN** a document processing attempt starts
- **THEN** the system creates a root span and stage spans for parse, chunking, embedding, multimodal, and postprocess

#### Scenario: Frontend loads trace drawer
- **WHEN** the frontend opens a document trace drawer
- **THEN** the backend returns the latest database span tree ordered by parent-child relationship and start time

### Requirement: Subspan And Generation Tracking
The span tracker SHALL support child spans under stages for concrete work such as parser calls, chunking strategy attempts, embedding batches, image OCR/caption calls, summary generation, graph extraction, and question generation.

#### Scenario: Embedding batch is traced
- **WHEN** indexing sends an embedding batch to a provider
- **THEN** the system records a generation or subspan with bounded input/output metadata, duration, status, and provider-safe error details

### Requirement: Retry Re-entry And Abort Semantics
The span tracker SHALL support latest-attempt lookup, stale span superseding, descendant cancellation, all-open-span cancellation, and attempt finalization.

#### Scenario: Retry supersedes stale running span
- **WHEN** a retry re-enters a span name that is still marked running for the same attempt
- **THEN** the system cancels or supersedes the stale span before opening the replacement span

#### Scenario: Attempt abort closes open spans
- **WHEN** a document attempt is cancelled or aborted
- **THEN** the system marks all pending or running spans in that attempt as cancelled and finalizes the root span

### Requirement: Span Payload Safety
The system SHALL keep frontend-visible span payloads free of hidden reasoning, raw prompts, secrets, and unbounded provider payloads.

#### Scenario: Tool or generation span is exposed
- **WHEN** a span tree is returned to the frontend
- **THEN** the response contains sanitized metadata and bounded previews instead of raw confidential prompt or provider content

