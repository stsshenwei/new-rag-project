## Context

The backend now has several retrieval paths that can change answer behavior: Raw RAG with Milvus and SQLite FTS5, GraphRetriever, finite-state Agentic Retrieval, citation verification, and agentic chat streaming. The current test suite validates code behavior, but it does not provide a product-level evaluation loop for curated enterprise questions.

Evaluation must sit above the query stack. It should replay known questions, capture what the system did, score the result, and produce reports without mutating the knowledge corpus, feedback files, vector stores, graph data, or chat memory.

## Goals / Non-Goals

**Goals:**

- Provide a versioned evaluation dataset format for enterprise RAG, GraphRAG, and Agentic Retrieval behavior.
- Run evaluation cases through existing query services and capture full query snapshots.
- Score rule-based metrics for citation traceability, required source coverage, expected terms, graph path source traceability, tool plan matching, insufficient-evidence handling, and latency.
- Allow optional LLM-as-judge providers through stable interfaces without making them mandatory.
- Store eval runs and results durably in SQLite.
- Generate JSON and Markdown reports that are useful for regression review.
- Keep evaluation isolated from production query, ingest, feedback, and memory behavior.

**Non-Goals:**

- Do not build a frontend evaluation dashboard in this change.
- Do not add eval cases to the retrievable knowledge corpus.
- Do not write evaluation corrections into `backend/data/feedback/`.
- Do not require Neo4j, Milvus, or an LLM judge to be live for all tests.
- Do not replace unit tests or route tests; this suite complements them with scenario-level quality checks.
- Do not expose hidden chain-of-thought in evaluation reports.

## Decisions

### Decision 1: Store evaluation metadata in SQLite

Add tables such as `eval_run` and `eval_result` in the existing backend SQLite database boundary. Each run records dataset identity, config snapshot, status, timestamps, aggregate scores, report paths, and error details. Each result records the input case, captured answer fields, metric scores, latency, status, and failure reasons.

Alternative considered: store only JSON files. Rejected because runs need querying, comparison, and API inspection.

### Decision 2: Keep evaluation datasets as external JSON/YAML files

Evaluation cases should live outside `backend/data/` retrievable corpus. A sample dataset can be stored under a dedicated eval fixture directory, while operators can pass local dataset paths at runtime.

Alternative considered: make eval cases database-only. Rejected because file-based datasets are easier to review, version, and run in CI.

### Decision 3: Execute through the existing service contract

The first runner should call `RAGService.answer_query()` or an equivalent internal query function. This captures both legacy Raw RAG and Agentic `/rag/query` behavior depending on runtime configuration. It should not call low-level vector, keyword, or graph providers directly except for metric validation.

Alternative considered: run each retriever independently. Rejected for MVP because enterprise evaluation should measure the actual product path first.

### Decision 4: Use rule-based metrics as the default scorer

Rules can deterministically check whether citations resolve to `document_chunk`, whether required source chunks are used, whether graph paths carry source chunk ids, whether expected tools appear, whether required terms appear, and whether insufficient-evidence cases are handled correctly.

Optional judge providers can add semantic scoring later, but the suite must be useful without network access or model calls.

Alternative considered: rely on LLM-as-judge from the start. Rejected because it makes evaluation expensive, less deterministic, and harder to run in CI.

### Decision 5: Add provider interfaces for judges

Define interfaces such as `AnswerCorrectnessJudgeProvider`, `FaithfulnessJudgeProvider`, and `CitationJudgeProvider`. Provide no-op or rule-only defaults. OpenAI or other judges can be added behind those interfaces without changing the runner contract.

Alternative considered: call the OpenAI client directly from the runner. Rejected because all providers in this project should remain replaceable.

### Decision 6: Reports are artifacts, not source-of-truth

`EvaluationReporter` should generate JSON and Markdown reports from stored run results. The database remains the source of truth for API inspection and comparison. Reports are convenient review artifacts.

Alternative considered: only return API JSON. Rejected because Markdown reports are useful for local development, PR review, and audit trails.

## Risks / Trade-offs

- Evaluation can become slow if every case calls the full LLM answer path -> Add per-run limits, status tracking, latency metrics, and small sample datasets for CI.
- Semantic answer quality is hard to score deterministically -> Start with traceability and expected evidence metrics, then add optional judge providers.
- Dataset schemas can drift -> Validate dataset version and fail fast with clear case-level errors.
- Agent traces may contain sensitive prompt context -> Store and report bounded public trace fields only; do not persist raw prompts, memory dumps, or hidden reasoning.
- Graph metrics can fail when Neo4j is not configured -> Treat graph expectations as case-specific; skip or fail only cases that explicitly require graph evidence.
- Regression comparisons can be noisy with LLM output -> Compare stable structural metrics first, and keep semantic judge scores optional.

## Migration Plan

1. Add evaluation models and repository schema for `eval_run` and `eval_result`.
2. Add dataset loader and validator for JSON/YAML eval sets.
3. Add runner that executes cases through the existing query path and captures snapshots.
4. Add rule-based metrics and optional judge provider interfaces.
5. Add report generation for JSON and Markdown.
6. Add API routes or CLI commands for local execution and run inspection.
7. Add sample eval datasets and tests with fake providers.

Rollback is straightforward: disable or do not call `/eval/*` routes or CLI commands. Evaluation storage is additive and does not affect production ingest or query behavior.

## Open Questions

- Should the first implementation expose both API and CLI, or prioritize CLI for local/CI use and add API after?
- Should eval runs execute synchronously for MVP, or create queued background tasks immediately?
- Should report files be stored under `backend/eval_reports/`, `backend/data/eval_reports/`, or a configurable `EVAL_REPORT_DIR`?
