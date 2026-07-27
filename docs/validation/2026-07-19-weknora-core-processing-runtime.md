# Weknora Core Processing Runtime Validation

Date: 2026-07-19

Scope: `align-weknora-core-processing-runtime`

## Reference Behavior Checked

- Adaptive chunking fallback remains unchanged: `auto` can try heading, then heuristic, and must end with legacy; explicit heading/heuristic fall back to legacy; recursive/legacy remain legacy-only.
- Upload confirmation can use a durable SQLite-backed task queue with leases, retry scheduling, cancellation, and dead-letter records.
- Processing trace is represented as a SQLite span tree with root, stage, subspan, and generation nodes. Local files are retained as supplemental evidence.
- Prompt composition uses the YAML catalog for quick-answer context, reasoning agent prompts, query rewrite, intent, keyword extraction, summary generation, generated questions, titles, graph extraction, and fallback behavior.
- Retrieval keeps the dense + keyword + RRF + optional rerank base and adds conservative low-recall expansion, rerank degradation, MMR, duplicate removal, and debug metadata.
- Extended reasoning tools are feature-gated. Web, data analysis, database query, and skill execution boundaries return safe unavailable or scoped observations unless explicitly configured.
- Knowledge document cards show title, summary, date, type, processing state, Trace action, and delete action. Trace drawer reads the database span tree first and shows durable task status.

## Explicit Exclusions

- Wiki ingestion, wiki prompts, wiki tools, and wiki-specific retrieval are excluded from this change.
- Executable skill scripts are not enabled; `execute_skill` is a safety boundary stub.
- FAQ-specific retrieval is excluded.

## Manual Smoke Checklist

- Start backend with `PROCESSING_WORKER_ENABLED=true`, upload a document from the knowledge page, confirm processing, and verify a `document_processing_task` row is created before processing finishes.
- Restart backend with a pending or stale leased task and verify the worker claims and completes/retries it.
- Open the document Trace action and verify root/stage/subspan nodes appear from SQLite spans.
- Force a parser failure and verify retry state, dead-letter state, last error, and trace error are visible.
- Delete a processing document and verify task cancellation, open-span cancellation, SQLite chunk removal, and vector deletion.
- Query with `RETRIEVAL_DEBUG_ENABLED=true` and verify debug metadata includes query understanding, fusion, rerank/degradation, MMR, duplicate removal, parent recall, and context expansion fields when applicable.
- Use quick answer and intelligent reasoning modes to confirm prompt catalog rendering does not expose secrets, raw prompts, provider payloads, or hidden reasoning.

## Automated Validation

- `backend: .\.venv\Scripts\python.exe -m unittest tests.test_adaptive_chunker tests.test_document_chunker_structured tests.test_document_processing_fixtures tests.test_processing_config tests.test_processing_task_repository tests.test_processing_span_tracker tests.test_processing_worker tests.test_query_understanding tests.test_agent_runtime_prompts_tools tests.test_agent_runtime_loop tests.test_runtime_config tests.test_hybrid_retrieval tests.test_document_repository tests.test_rag_api_routes -v`
  - Result: passed, 148 tests.
- `backend: .\.venv\Scripts\python.exe -m unittest tests.test_rag_service_structured_ingest tests.test_agentic_chat_stream tests.test_agent_runtime_loop tests.test_rag_api_routes -v`
  - Result: passed, 60 tests.
- `frontend: npx tsc --noEmit`
  - Result: passed.
- `frontend: npm run build`
  - Result: compiled successfully and completed lint/type-check phase, then Next static-page generation worker exited on Windows with `VirtualAlloc failed` / code `3221225794`.
- `frontend: npm run lint`
  - Result: not usable as a non-interactive check because `next lint` prompted to configure ESLint.
