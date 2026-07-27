## 1. Baseline Audit And Guardrails

- [x] 1.1 Add a Weknora parity reference note that maps current Python modules to Weknora source areas for chunking, spans, queue, prompts, retrieval, and tools.
- [x] 1.2 Add UTF-8 integrity checks for prompt templates, regex-bearing chunking files, tool observations, and Chinese UI/backend labels.
- [x] 1.3 Add adaptive chunking parity tests for auto heading, auto heuristic, explicit heading, explicit heuristic, recursive, and legacy strategy chains.
- [x] 1.4 Add chunking fixtures for Chinese punctuation, Chinese chapter markers, Markdown headings, heuristic markers, protected code/formula/table/image regions, and long protected spans.
- [x] 1.5 Add parent-child chunking tests for context headers, source offsets, deterministic parent-child IDs, and identical single-child collapse behavior.

## 2. Durable Processing Queue Schema

- [x] 2.1 Extend SQLite metadata schema with durable processing task and dead-letter tables, indexes, schema-version handling, and clean-rebuild messaging.
- [x] 2.2 Implement a processing task repository with create, claim, heartbeat/lease refresh, complete, retry, cancel, dead-letter, and stale-lease recovery operations.
- [x] 2.3 Add configuration for worker enablement, poll interval, lease timeout, retry budgets, retry backoff, and max concurrent tasks.
- [x] 2.4 Add unit tests for task creation, deterministic task IDs, claim ordering, stale lease recovery, retry scheduling, cancellation, and dead-letter insertion.

## 3. Durable Processing Worker

- [x] 3.1 Implement a local durable processing worker loop that claims runnable tasks and dispatches parse, chunk, embedding, multimodal, and postprocess work.
- [x] 3.2 Wire upload confirmation to enqueue durable tasks before returning processing-started state.
- [x] 3.3 Make processing writes idempotent for document records, chunks, vectors, derived artifacts, task attempts, and status updates.
- [x] 3.4 Add cancellation checks at stage boundaries and before writing derived evidence.
- [x] 3.5 Add restart recovery behavior for pending, retrying, and stale leased tasks.
- [x] 3.6 Add integration tests for upload confirm, worker success, worker crash simulation, retry, dead-letter, and cancellation.

## 4. Weknora-Style Span Tracker

- [x] 4.1 Extend the span repository/tracker with `latest_attempt`, `lookup_stage`, `lookup_span_by_name`, `begin_subspan`, `finalize_attempt`, `abort_attempt`, `cancel_descendants`, and `cancel_all_open_spans`.
- [x] 4.2 Add retry re-entry handling that supersedes stale running spans with the same name in the same attempt.
- [x] 4.3 Add heartbeat timestamp updates for active processing attempts and stage/subspan transitions.
- [x] 4.4 Trace parser calls, chunk strategy attempts, embedding batches, multimodal provider calls, summary generation, graph extraction, and question generation as subspans or generation spans.
- [x] 4.5 Update trace tree APIs to read from database spans and keep file artifacts as supplemental evidence only.
- [x] 4.6 Add frontend trace drawer compatibility for root/stage/subspan/generation tree nodes and sanitized metadata.
- [x] 4.7 Add tests for span tree shape, subspan insertion, generation spans, abort semantics, descendant cancellation, retry superseding, heartbeat, and sanitized trace output.

## 5. Prompt Template Catalog Completion

- [x] 5.1 Add adapted Weknora prompt YAML files for system prompt, context template, rewrite, intent prompts, keyword extraction, summary generation, generated questions, session title, graph extraction, and fallback.
- [x] 5.2 Extend the prompt template loader to validate required template IDs, mode compatibility, placeholders, default language, and malformed YAML errors.
- [x] 5.3 Wire query rewrite, intent detection, keyword extraction, summary generation, generated question/title generation, graph extraction, fallback responses, quick answer context, and reasoning agent prompts through the catalog.
- [x] 5.4 Add safe fallback behavior for missing optional templates and hard failure behavior for missing required templates.
- [x] 5.5 Add golden rendering tests that verify user question, selected knowledge base, conversation history, retrieved context, tools, skills, and language are composed correctly.
- [x] 5.6 Add tests that prompt rendering never exposes secrets, raw provider payloads, or hidden reasoning content.

## 6. Retrieval Quality Controls

- [x] 6.1 Add low-recall query expansion after initial dense/keyword retrieval when candidate counts or scores are below configured thresholds.
- [x] 6.2 Add rerank threshold degradation and bounded top-candidate fallback when reranking filters all useful evidence.
- [x] 6.3 Add MMR diversity selection after fusion/rerank with configurable relevance and diversity weights.
- [x] 6.4 Strengthen exact and near-duplicate removal using stable IDs, content signatures, parent relationships, and overlap thresholds.
- [x] 6.5 Expand retrieval debug metadata for query understanding, expansion, dense hits, keyword hits, fusion, rerank, degradation, MMR, duplicate removal, parent recall, and context expansion.
- [x] 6.6 Add configuration defaults and examples for expansion thresholds, rerank degradation, MMR, duplicate thresholds, and debug toggles.
- [x] 6.7 Add retrieval tests for low-recall expansion, rerank degradation, MMR ordering, duplicate removal, parent recall compatibility, and debug trace structure.

## 7. Extended Agent Runtime Tools

- [x] 7.1 Add feature-gated tool registration for web search, web fetch, data analysis, database query, and executable skill boundary behavior.
- [x] 7.2 Implement disabled/unavailable observations for every extended tool when configuration or provider dependencies are absent.
- [x] 7.3 Implement web search and web fetch adapters with allowlists, timeouts, output limits, content extraction, and sanitized traces.
- [x] 7.4 Implement read-only data analysis and database query boundaries with explicit data-source scope and unauthorized-source rejection.
- [x] 7.5 Keep executable skill scripts disabled unless a secure sandbox is implemented, and return stable unavailable observations when requested.
- [x] 7.6 Emit sanitized tool trace events and backend spans for tool name, bounded arguments, status, duration, error class, and output summary.
- [x] 7.7 Add tests for tool gating, unavailable observations, web safety limits, database scope rejection, skill execution disabled behavior, timeout handling, and trace sanitization.

## 8. UI And API Integration

- [x] 8.1 Update document status APIs to expose durable task status, retry/dead-letter state, latest attempt, and summary availability.
- [x] 8.2 Update knowledge document cards to show title, summary, date, type, processing state, trace action, and delete action using backend summary/status fields.
- [x] 8.3 Update trace drawer data loading to use database span tree while linking to parsed/chunk/report artifacts when available.
- [x] 8.4 Ensure deletion cancels queued/active tasks, closes open spans, removes derived vectors/chunks, and returns actionable errors when cleanup fails.
- [x] 8.5 Add frontend compatibility checks for document card states, trace drawer states, failed/dead-letter documents, and summary display.

## 9. Documentation And Validation

- [x] 9.1 Update backend architecture/design docs for durable processing, span trace, prompt catalog, retrieval controls, and extended tools.
- [x] 9.2 Update `.env.example`, `rag_config.example.yaml`, and README setup notes for new queue, prompt, retrieval, and tool settings.
- [x] 9.3 Add clean-rebuild guidance for any incompatible schema version changes.
- [x] 9.4 Run backend unit tests for chunking, queue, spans, prompts, retrieval, tools, and deletion.
- [x] 9.5 Run backend integration smoke tests for upload processing, restart recovery, trace tree, summary display, retrieval debug, quick chat, and reasoning mode.
- [x] 9.6 Run frontend lint/build or targeted checks for knowledge document cards and trace drawer compatibility.
- [x] 9.7 Record manual validation notes comparing current behavior against Weknora reference behavior, explicitly marking wiki features as excluded.
