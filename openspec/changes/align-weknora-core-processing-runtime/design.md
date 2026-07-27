## Context

The project now has Weknora-inspired adaptive parsing/chunking, document trace files, SQLite processing spans, prompt-backed reasoning, hybrid retrieval, and a first safe set of agent tools. The remaining gap is not one isolated feature; it is the runtime discipline around those pieces. Weknora treats document processing as a durable task pipeline, records detailed span trees in the database, drives agent/retrieval behavior from a full prompt catalog, and applies retrieval quality controls after fusion and rerank.

This design keeps the Python/FastAPI/SQLite/Milvus architecture. It does not port Weknora's Go services directly. The goal is to adapt the useful boundaries: durable queue semantics, span lifecycle, prompt catalog completeness, retrieval parity controls, and tool safety.

The adaptive chunking fallback strategy is a hard invariant. The implementation may add tests, diagnostics, and bug fixes, but it must not change the degradation chain.

## Goals / Non-Goals

**Goals:**

- Replace process-local upload processing with a durable processing task runtime that survives restart and records retry/dead-letter state.
- Upgrade `knowledge_processing_spans` from stage-only usage to Weknora-style root/stage/subspan/generation trees.
- Preserve and guard the adaptive chunking fallback invariant with parity tests.
- Complete the prompt template catalog needed for context construction, rewriting, keywords, summaries, titles, generated questions, graph extraction, and fallback behavior.
- Improve document retrieval quality with MMR, rerank degradation, near-duplicate removal, low-recall query expansion, and structured debug trace.
- Extend non-wiki agent tools behind explicit configuration and safe unavailable behavior.
- Keep frontend trace views backed by database span trees rather than file-only trace artifacts.

**Non-Goals:**

- Do not introduce wiki prompts, wiki tools, or wiki ingestion.
- Do not replace FastAPI with Weknora's Go services.
- Do not require Redis/Postgres in the first implementation unless the durable queue design explicitly cannot meet lifecycle requirements with SQLite.
- Do not change the user-visible quick answer mode semantics except where prompt/context templates are shared safely.
- Do not expose hidden chain-of-thought, raw prompts, provider secrets, or unsanitized tool payloads in UI trace.
- Do not alter the chunking degradation order.

## Decisions

### Decision: Start with a SQLite-backed durable queue

Document processing will use a SQLite task table with deterministic task identifiers, task type, scope, payload, status, attempt counts, next-run time, lease owner, lease deadline, error fields, and timestamps. A local worker loop will claim runnable tasks, refresh leases during long work, and release/retry/dead-letter tasks based on configured policies.

This keeps the deployment simple while giving upload processing restart recovery and traceable lifecycle. The schema should not prevent a later Redis/Celery/Asynq adapter; queue operations should live behind a small repository/service boundary.

Alternative considered: keep FastAPI `BackgroundTasks`. This keeps implementation small, but tasks disappear on process restart and cannot support dead-letter or robust cancellation.

### Decision: Treat processing stages and sub-work as database spans

Each processing attempt will open a root span and predefined stage spans for parse, chunk, embedding, multimodal, and postprocess. Stage implementations may open subspans and generation spans for concrete work: parser engine calls, chunking strategy attempts, embedding batches, image OCR/caption calls, summary generation, graph extraction, and question generation.

The tracker will support `begin_subspan`, `lookup_stage`, `lookup_span_by_name`, `finalize_attempt`, `abort_attempt`, `cancel_descendants`, `cancel_all_open_spans`, and `latest_attempt`. Retry re-entry will supersede stale running spans with the same name within the same attempt before opening a replacement.

Alternative considered: continue writing `trace.json`, `parsed.md`, and `chunks.jsonl` as the primary trace. Files are still useful evidence artifacts, but they are not queryable enough for UI trace, retries, and operations.

### Decision: Preserve chunking behavior and test it as an invariant

The current strategy selector already mirrors Weknora's fallback chain. This change will not rewrite the selector. It will add parity fixtures and assertions for strategy chain, selected tier, rejected tier reasons, Chinese punctuation, Chinese chapter markers, protected blocks, heading breadcrumbs, heuristic boundaries, legacy fallback, and parent-child collapse behavior.

Alternative considered: port Weknora chunker line-by-line. That would risk accidental behavior drift in a working Python implementation and would blur the explicit invariant the user has asked to preserve.

### Decision: Make prompt templates a catalog, not scattered constants

The prompt service will load a complete adapted catalog from `backend/config/prompt_templates/`. Template identifiers, required placeholders, default language, mode compatibility, and safe rendering rules will be validated at startup. Existing hardcoded prompt fragments for query understanding, rewrite, keywords, summaries, fallback, and graph extraction should move behind this catalog when they affect model calls.

Alternative considered: copy YAML files without wiring. That would satisfy file presence but not the user's real concern: how user questions, retrieved context, and generation instructions are composed.

### Decision: Add retrieval controls after the existing hybrid foundation

The existing dense + keyword + RRF + rerank + parent recall path remains the base. This change adds Weknora-style controls around it: low-recall query expansion, rerank threshold degradation, MMR diversity selection, stronger exact and near-duplicate removal, and detailed retrieval trace entries explaining which controls changed candidate order.

FAQ-specific retrieval stays out of scope because the user explicitly deferred it.

### Decision: Gate risky tools and expose unavailable observations

Additional tools such as web search, web fetch, data analysis, database query, and skill execution boundaries will be registered only when configuration and provider dependencies allow safe execution. Disabled tools return stable unavailable observations rather than failing the whole agent run. Tools must emit sanitized trace spans and respect per-tool timeouts and output limits.

Alternative considered: enable all Weknora tools by default. That would expand security and dependency surface too quickly, especially for web, database, and executable skill operations.

## Risks / Trade-offs

- [Risk] SQLite queue workers can compete or leave stale leases after crashes. -> Mitigation: use lease deadlines, stale-lease recovery, deterministic task IDs, transaction-protected claims, and startup recovery tests.
- [Risk] Retried stages can produce duplicate vectors or documents. -> Mitigation: make indexing idempotent by document/chunk IDs, supersede stale spans, and use task attempt metadata in debug logs.
- [Risk] Full span trees can grow quickly for large PDFs. -> Mitigation: bound generation/subspan fanout, aggregate embedding batches, and keep large evidence in artifacts or metadata references rather than span payloads.
- [Risk] Prompt template drift can silently change answers. -> Mitigation: validate required template IDs and placeholders, add golden rendering tests, and keep a default fallback template for safe startup failure messages.
- [Risk] Retrieval controls can reduce recall if tuned too aggressively. -> Mitigation: ship conservative defaults, emit debug traces, and add evaluation fixtures before enabling strict thresholds.
- [Risk] Web/database/tool execution can create security problems. -> Mitigation: keep disabled by default, require explicit configuration, enforce allowlists, sanitize outputs, and trace unavailable states.

## Migration Plan

1. Add new queue, dead-letter, and span schema with a schema version bump and clean-rebuild guidance if incompatible with existing metadata storage.
2. Implement queue repository/service and worker loop behind disabled-by-default configuration.
3. Add span tracker APIs and migrate processing trace drawer reads to the database span tree while keeping trace files as optional artifacts.
4. Add chunking parity tests before touching any chunking code.
5. Add prompt templates and render tests, then replace model-call prompt construction one path at a time.
6. Add retrieval quality controls behind configuration and debug output.
7. Add extended tools behind explicit feature flags and unavailable observations.
8. Enable the durable processing runtime in development, validate upload/retry/cancel/restart behavior, then make it the default.

Rollback is configuration-based for runtime behavior: disable the durable worker and extended tools to fall back to current synchronous/background execution paths where still present. Schema rollback should use the existing clean-rebuild CLI because processing/runtime schema is not expected to be backward compatible.

## Open Questions

- Should the first durable queue implementation be SQLite-only, or should Redis/Celery be introduced immediately for production parity?
- What retry budgets should each stage use: parser, chunking, embedding, multimodal, and postprocess?
- Which web search/fetch provider should be supported first, and should it be available to all users or only local development?
- Should database query tools target only project SQLite metadata, or should external business databases be supported later through a separate approval system?
- Should generated summary/question/title tasks run as part of postprocess by default, or only when enrichment providers are configured?
