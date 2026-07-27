## 1. Evaluation Models And Storage

- [x] 1.1 Add evaluation domain models for dataset metadata, eval case, expected evidence, eval run, eval result, metric score, judge score, and report metadata.
- [x] 1.2 Add SQLite schema for `eval_run` with dataset id/version, status, timestamps, configuration snapshot, aggregate scores, report paths, and error message.
- [x] 1.3 Add SQLite schema for `eval_result` with run id, case id, status, answer snapshot, evidence snapshot, metric scores, latency, and error details.
- [x] 1.4 Implement `EvaluationRepository` with create/update/list/get operations for runs and results.
- [x] 1.5 Add repository tests for schema creation, run lifecycle updates, result persistence, and JSON field round trips.

## 2. Dataset Loading And Validation

- [x] 2.1 Implement `EvaluationDatasetLoader` for JSON eval datasets.
- [x] 2.2 Add optional YAML dataset loading when PyYAML is installed, with clear fallback errors when it is unavailable.
- [x] 2.3 Validate dataset schema version, dataset id/name/version, case ids, required questions, tags, filters, and expectation fields.
- [x] 2.4 Enforce dataset path safety so eval loading cannot read arbitrary unsafe paths.
- [x] 2.5 Add a small sample enterprise eval dataset covering fact, source, dependency, impact, troubleshooting, and insufficient-evidence cases.
- [x] 2.6 Add dataset loader tests for valid datasets, invalid schema versions, missing required fields, optional expectations, and path safety.

## 3. Evaluation Runner

- [x] 3.1 Implement `EvaluationRunner` that creates a run, executes selected cases, records latency, and persists result snapshots.
- [x] 3.2 Execute cases through the existing `RAGService.answer_query()` path so runtime configuration controls Raw RAG or Agentic Retrieval behavior.
- [x] 3.3 Capture answer, citations, used chunks, used entities, graph paths, confidence, agent trace, tool calls, evidence summary, and debug metadata.
- [x] 3.4 Continue a run after individual case failures and mark failed results without stopping remaining cases.
- [x] 3.5 Mark runs as completed, partial_failed, failed, or cancelled based on result statuses.
- [x] 3.6 Add runner tests with fake RAG services for successful cases, failing cases, partial failures, and captured snapshots.

## 4. Metrics And Judge Providers

- [x] 4.1 Implement rule-based metric scorer for citation resolvability using `CitationVerifier` and `DocumentRepository`.
- [x] 4.2 Implement required source coverage, expected answer term coverage, insufficient-evidence correctness, graph path traceability, expected tool match, forbidden tool match, and latency metrics.
- [x] 4.3 Define judge provider interfaces for answer correctness, faithfulness, and citation quality.
- [x] 4.4 Add default no-op or rule-only judge provider implementations so eval runs work without external LLM calls.
- [x] 4.5 Merge rule metric scores and optional judge scores into each eval result without letting judge scores replace deterministic scores.
- [x] 4.6 Add scorer tests for citation failures, missing expected sources, graph path source chunk failures, expected tool mismatches, and insufficient-evidence cases.

## 5. Reporting And Regression Comparison

- [x] 5.1 Implement aggregate score calculation for eval runs.
- [x] 5.2 Implement JSON report generation with run metadata, aggregate scores, and per-case result details.
- [x] 5.3 Implement Markdown report generation with summary tables, failed cases, evidence failures, graph failures, tool mismatches, and latency notes.
- [x] 5.4 Add baseline comparison support for metric deltas, newly failed cases, fixed cases, and latency changes.
- [x] 5.5 Make report output directory configurable with a safe default.
- [x] 5.6 Add report tests for JSON output, Markdown output, and baseline comparison summaries.

## 6. API Or CLI Integration

- [x] 6.1 Add request/response schemas for starting eval runs, listing runs, inspecting run details, and listing run results.
- [x] 6.2 Add `/eval/runs` endpoint or CLI command to start a run from a dataset path with optional case filters and baseline run id.
- [x] 6.3 Add run listing and run detail interfaces that return metadata, aggregate scores, report paths, and result summaries.
- [x] 6.4 Ensure eval interfaces do not mutate document ingest, feedback files, memory, chat conversations, vector stores, or graph data.
- [x] 6.5 Add API or CLI tests for starting runs, rejecting unsafe dataset paths, listing runs, inspecting results, and production isolation.

## 7. Documentation And Configuration

- [x] 7.1 Add environment/config documentation for eval dataset directories, report directories, judge provider selection, and run limits.
- [x] 7.2 Update `docs/ARCHITECTURE.md` with the evaluation suite position above Raw RAG, GraphRetriever, and Agentic Retrieval.
- [x] 7.3 Update `docs/design-docs/backend-rag-pipeline.md` or add a new eval design doc explaining how eval replay differs from production query.
- [x] 7.4 Update `docs/DEVELOPMENT.md` with commands for running eval unit tests and a sample eval run.
- [x] 7.5 Update README with a concise enterprise evaluation suite usage note.

## 8. Validation

- [x] 8.1 Run evaluation model, repository, dataset loader, scorer, runner, reporter, and API/CLI tests.
- [x] 8.2 Run existing RAG, Agentic Retrieval, GraphRetriever, citation verifier, and chat stream regression tests.
- [x] 8.3 Run full backend test suite.
- [x] 8.4 Verify OpenSpec apply status reports all tasks before marking the change ready for archive.
