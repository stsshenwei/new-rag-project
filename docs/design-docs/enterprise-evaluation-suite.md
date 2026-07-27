# Enterprise Evaluation Suite

## Purpose

The evaluation suite gives the RAG system a repeatable quality loop. It replays curated enterprise questions, captures the answer and evidence shape, scores deterministic metrics, and writes reports that can be compared across changes.

## Runtime Shape

```text
evalset.json/yaml
  -> EvaluationDatasetLoader
  -> EvaluationRunner
  -> RAGService.answer_query()
  -> RuleBasedEvaluationScorer
  -> EvaluationRepository
  -> EvaluationReporter
```

The suite measures the product query path. It does not call vector, keyword, or graph providers directly except when metrics need to validate returned evidence.

## Isolation Rules

- Evalsets are not stored under `backend/data/` by default.
- Evalsets are not ingested into Milvus, FTS5, graph extraction, feedback files, or memory storage.
- Runs store snapshots in `eval_run` and `eval_result`.
- Reports are generated artifacts, not the source of truth.

## Metrics

The default scorer is rule-based and offline:

- citation resolvability through `document_chunk`
- required source hit rate
- expected answer term coverage
- graph path relation `source_chunk_id` traceability
- expected and forbidden tool usage
- insufficient-evidence correctness
- latency capture

Optional judge providers can add semantic scores later without replacing deterministic scores.

## API

- `POST /eval/runs`
- `GET /eval/runs`
- `GET /eval/runs/{run_id}`
- `GET /eval/runs/{run_id}/results`
