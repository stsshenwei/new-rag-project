# Weknora Core Parity Map

This note records where the Python project mirrors Weknora behavior and where the remaining parity work belongs. It is intentionally implementation-facing: each row points future changes at the owning module instead of scattering Weknora references through code comments.

## Source Areas

| Capability | Current project owner | Weknora reference area | Parity note |
| --- | --- | --- | --- |
| Adaptive chunking strategy | `backend/app/services/adaptive_chunker.py` | `internal/infrastructure/chunker/strategy.go`, `profiler.go`, `validator.go` | The degradation invariant is fixed: auto may try heading, then heuristic, and always ends in legacy; explicit heading/heuristic fall back to legacy; recursive/legacy are legacy-only. |
| Heading and heuristic splitting | `backend/app/services/adaptive_chunker.py` | `heading_splitter.go`, `heuristic_splitter.go`, `patterns.go` | Python keeps equivalent tiers and diagnostics, with parity tests covering Chinese chapters, protected spans, breadcrumbs, and rejection fallback. |
| Parent-child document chunks | `backend/app/services/document_chunker.py` | `splitter.go`, `strategy.go` `SplitParentChild` | Parents are stored for context recall; child/table/ocr/image chunks are retrievable evidence. Identical child collapse is represented with metadata and guarded by tests. |
| Document parsing | `backend/app/services/document_parser.py`, `parser_engine_registry.py` | `internal/infrastructure/docparser/*` | Python supports builtin parsers and optional providers; full Weknora parser-provider breadth is out of scope until explicitly added. |
| Processing task lifecycle | `backend/app/services/rag_service.py`, future durable task repository/worker | `internal/router/task.go`, `internal/types/task.go`, task queue repositories | Current upload processing is process-local background work; parity work adds durable queue, retry, cancellation, dead-letter, and restart recovery. |
| Processing spans | `backend/app/services/processing_span_tracker.py`, `processing_trace.py` | `internal/application/service/knowledge_span_tracker.go`, `internal/application/repository/knowledge_span_repo.go` | Current database spans cover root/stages; parity work adds subspans, generation spans, retry re-entry, abort, heartbeat, and tree-first UI trace. |
| Prompt templates | `backend/config/prompt_templates/`, `backend/app/services/agent_prompt_templates.py` | `config/prompt_templates/*.yaml` | Current catalog contains agent/context templates only; parity work adds rewrite, intent, keyword, summary, questions, session title, graph, fallback, and safety validation. |
| Retrieval strategy | `backend/app/services/rag_service.py`, `retrieval_planner.py`, `reranker.py` | `internal/application/service/chat_pipeline/search.go`, `rerank.go` | Current dense/keyword/RRF/rerank/parent recall foundation remains; parity work adds low-recall expansion, rerank degradation, MMR, stronger near-duplicate removal, and richer debug trace. |
| Agent runtime tools | `backend/app/services/agent_runtime_tools.py`, `agent_runtime.py` | `internal/agent/tools/*`, `config/agent_type_presets.yaml` | Current non-wiki document tools are safe/read-only. Parity work adds config-gated web/data/database/tool-boundary behavior while wiki remains excluded. |

## Non-Negotiable Invariants

- Chunking fallback order must not change.
- Wiki tools, prompts, and ingestion are excluded from this parity track.
- Raw prompts, hidden reasoning, secrets, and unbounded provider payloads must not be exposed in frontend trace.
- Parent chunks provide context recall; retrievable evidence remains child/table/ocr/image-derived chunks unless a later spec changes that contract.
- Prompt-bearing files and regex-bearing files must remain valid UTF-8 and readable for Chinese product documents.

## Validation Pointers

- Chunking guardrails live in `backend/tests/test_adaptive_chunker.py`.
- Parent-child and collapsed-child guardrails live in `backend/tests/test_document_chunker_structured.py`.
- UTF-8 prompt/source integrity lives in `backend/tests/test_utf8_integrity.py`.
- Processing queue/span/retrieval/tool parity tests should be added beside the owning services as those later tasks are implemented.
