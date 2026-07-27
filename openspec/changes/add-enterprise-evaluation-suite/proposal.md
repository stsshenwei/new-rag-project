## Why

The project now has Raw RAG, keyword search, GraphRetriever, and a finite-state Agentic Retrieval workflow, but there is no repeatable way to measure whether changes improve answer quality, citation faithfulness, graph traceability, or tool behavior. An enterprise knowledge base needs an evaluation suite so retrieval, graph, and agent changes can be replayed, scored, compared, and audited before they reach users.

## What Changes

- Add an enterprise evaluation dataset format for curated questions, expected sources, expected entities, expected graph paths, expected tools, tags, and query types.
- Add durable evaluation run and result storage so each run records query snapshots, answer metadata, citations, graph paths, agent traces, tool calls, confidence, latency, and metric scores.
- Add an `EvaluationRunner` service that executes eval cases through existing query paths without changing production ingest or chat behavior.
- Add rule-based metrics for citation resolvability, required source coverage, expected term coverage, graph path traceability, insufficient-evidence behavior, tool-plan match, and latency.
- Add optional judge provider interfaces for answer correctness, faithfulness, and citation quality, with a default no-op or rule-only implementation so evaluation does not require an LLM judge.
- Add report generation for JSON and Markdown summaries, including failed cases, regressions, and per-metric aggregates.
- Add backend APIs or CLI entry points for creating runs, listing runs, inspecting results, and running an eval set locally.
- Keep evaluation isolated from knowledge ingest, feedback write-back, and user-facing query behavior.

## Capabilities

### New Capabilities

- `evaluation-datasets`: Defines the evaluation case schema, dataset loading, validation, and versioned metadata.
- `evaluation-execution`: Runs evaluation cases through existing RAG and Agentic Retrieval query paths while capturing query snapshots.
- `evaluation-metrics`: Scores answers, citations, graph paths, tool usage, sufficiency behavior, and latency with rule-based and optional judge-provider metrics.
- `evaluation-reporting`: Stores eval runs/results and generates JSON/Markdown reports with aggregate scores and regression summaries.
- `evaluation-api`: Exposes backend endpoints or CLI commands for running eval sets and inspecting runs without affecting production query behavior.

### Modified Capabilities

- None.

## Impact

- Backend models: new evaluation case, run, result, metric, score, report, and judge result models.
- Backend storage: new SQLite tables for eval runs/results and optional eval dataset metadata.
- Backend services: new dataset loader, evaluation runner, metric scorer, report generator, judge provider interfaces, and optional CLI module.
- Backend APIs: new `/eval/*` routes or an equivalent CLI entry point for controlled evaluation runs.
- Existing query stack: `RAGService.answer_query()`, `AgenticRetrievalWorkflow`, `CitationVerifier`, `DocumentRepository`, and graph retrieval are reused but not replaced.
- Docs/tests: new design documentation, sample eval dataset, unit tests, API/CLI tests, and regression coverage for citation, graph, and agent metrics.
