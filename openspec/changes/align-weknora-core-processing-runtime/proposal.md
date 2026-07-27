## Why

The project has already adopted several Weknora-inspired pieces, but the core runtime is still partial: document processing uses process-local background work, span trace is mostly stage-level, prompt templates are incomplete, retrieval lacks several Weknora parity controls, and the reasoning agent exposes only the first group of safe knowledge tools. This change closes those gaps as a coherent backend capability upgrade while preserving the existing chunking fallback invariant.

## What Changes

- Add a durable document processing runtime that can enqueue upload parsing, chunking, indexing, multimodal, and postprocess work with retries, dead-letter records, cancellation, and restart recovery.
- Upgrade SQLite span trace to Weknora-style processing spans with root/stage/subspan/generation nodes, retry re-entry handling, abort/cancel semantics, heartbeat timestamps, and frontend span-tree querying.
- Preserve the existing adaptive chunking degradation strategy exactly: `auto` may try heading, then heuristic, and must always end in legacy; explicit heading/heuristic must fall back to legacy; recursive/legacy must remain legacy-only.
- Add parity tests and diagnostics for Chinese punctuation, Chinese chapter markers, Markdown headings, heuristic markers, protected regions, parent-child chunking, and fallback rejection reasons.
- Complete the prompt template catalog by adding adapted Weknora templates for system prompts, context rendering, rewrite, intent, keyword extraction, summary generation, question generation, session title generation, graph extraction, and fallback behavior.
- Extend document retrieval with Weknora-style quality controls, including MMR diversity selection, rerank threshold degradation, stronger near-duplicate removal, low-recall query expansion, and richer retrieval debug trace. FAQ-specific retrieval remains out of scope.
- Extend the reasoning agent with additional non-wiki tools where safe: web search/fetch behind explicit configuration, data analysis, database query, skill execution boundary stubs, and richer tool/span trace integration.
- Keep wiki tools, wiki prompts, and wiki ingestion out of scope.
- Add encoding and prompt-content validation so Chinese prompts, regexes, labels, and tool observations cannot silently degrade into mojibake.

## Capabilities

### New Capabilities

- `durable-document-processing-runtime`: Covers persistent upload/document processing tasks, retry, dead-letter, cancellation, restart recovery, and processing-stage lifecycle.
- `weknora-processing-span-trace`: Covers span table behavior, span tree shape, subspans, generations, heartbeat, abort/cancel semantics, and frontend trace retrieval.
- `weknora-prompt-template-catalog`: Covers YAML prompt template loading and rendering for Weknora-style system, context, rewrite, intent, keyword, summary, question, title, graph, and fallback templates.
- `weknora-retrieval-quality-controls`: Covers document retrieval parity controls beyond the completed retrieval strategy, including MMR, rerank degradation, low-recall expansion, near-duplicate removal, and traceability.
- `extended-agent-runtime-tools`: Covers additional non-wiki reasoning tools, configuration gates, safety boundaries, trace events, and unavailable-tool behavior.
- `chunking-parity-guardrails`: Covers the immutable adaptive chunking fallback invariant and parity diagnostics/tests that prevent regression.

### Modified Capabilities

None.

## Impact

- Backend processing orchestration in `backend/app/services/rag_service.py`, upload confirmation routes in `backend/app/main.py`, and document processing state handling.
- SQLite schema and repositories for processing tasks, dead letters, spans, documents, summaries, and trace lookup.
- Span tracking services in `backend/app/services/processing_span_tracker.py` and related trace/report generation.
- Prompt files under `backend/config/prompt_templates/` and prompt loader/rendering services.
- Retrieval orchestration in `backend/app/services/rag_service.py`, `retrieval_planner.py`, reranker integration, context assembly, and retrieval debug payloads.
- Agent runtime and tools in `backend/app/services/agent_runtime.py`, `agent_runtime_tools.py`, skill handling, tool trace emission, and configuration.
- Frontend trace drawer and document-card status displays for processing/subspan states and generated summaries.
- Tests for durable task lifecycle, span tree semantics, chunking parity, prompt rendering, retrieval quality controls, agent tool safety, and UTF-8 content integrity.
