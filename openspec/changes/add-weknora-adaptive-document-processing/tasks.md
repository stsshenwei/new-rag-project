## 1. Baseline And Configuration

- [x] 1.1 Add focused regression tests that expose the current unreachable Docling conversion/OCR control flow and fixed character-slicing behavior before replacing them.
- [x] 1.2 Add explicit parser, PDF render, adaptive chunking, parent-child, media storage, preview, OCR, and caption settings with safe environment defaults and validation.
- [x] 1.3 Add `pypdfium2` and the approved builtin-format dependencies to `backend/requirements.txt` without making optional parser or multimodal providers startup requirements.
- [x] 1.4 Define stable processing version, parser error codes, chunk strategy/type enums, and requested/effective configuration schemas.

## 2. Parser Domain And Engine Registry

- [x] 2.1 Extend parsed document models with canonical Markdown, parsed images, parser diagnostics, page/layout provenance, warnings, and timing metadata.
- [x] 2.2 Implement `ParserEngineRegistry` resolution, normalized extension mapping, availability probes, builtin fallback, and requested/effective provenance.
- [x] 2.3 Implement and register tested builtin Markdown, DOCX, Excel, and image parsers while preserving existing path and file-size safety checks.
- [x] 2.4 Register Docling as a lazy optional engine, fix its conversion control flow, and make failure/fallback behavior explicit instead of silently returning empty content.
- [x] 2.5 Add unit tests for default builtin selection, optional engine selection, unsupported formats, unavailable engines, fallback reporting, and startup without optional dependencies.

## 3. Builtin Hybrid PDF Parser

- [x] 3.1 Implement safe `pypdfium2` document lifecycle, password/corruption/limit errors, PDFium locking policy, and deterministic native-handle cleanup.
- [x] 3.2 Implement page text extraction, image-area measurement, native/scanned classification, and force-scanned override with configurable thresholds.
- [x] 3.3 Implement plain-text quality checks, layout-aware reading-order fallback, conservative Markdown heading promotion, text cleanup, and repeating header/footer filtering.
- [x] 3.4 Implement eligible vector-figure clipping and page-position provenance during the native-text pass.
- [x] 3.5 Implement selective scanned-page JPEG rendering with DPI, quality, maximum-edge, memory, and dedicated concurrency limits.
- [x] 3.6 Implement eligible embedded-image extraction from native pages with filtering for trivial assets and stable page/resource identifiers.
- [x] 3.7 Assemble native Markdown and scanned/embedded/vector image references in page order and populate complete parse diagnostics.
- [x] 3.8 Implement policy-controlled render-all fallback for unexpected routing failures while keeping password, corruption, and limit failures explicit.
- [x] 3.9 Add native, scanned, mixed, malformed-text-layer, force-scanned, password-protected, figure-bearing, limit, and concurrent PDF tests.

## 4. Image Storage And Provenance

- [x] 4.1 Define an `ObjectStorageProvider` contract for put, read, delete, existence, and scoped resource metadata.
- [x] 4.2 Implement a path-safe local media provider with generated keys, configured root enforcement, bounded writes, and no base64 persistence in SQLite.
- [x] 4.3 Add final SQLite image resource and image operation tables/columns with workspace, KB, document, page, source type, ownership, status, and provider provenance.
- [x] 4.4 Add repository methods for transactional image ownership, scoped lookup, deletion, retry state, and cleanup of abandoned staged resources.
- [x] 4.5 Add tests for traversal rejection, cross-KB isolation, cancellation cleanup, document deletion, partial failure, and missing resource handling.

## 5. Document Profiling And Recursive Foundation

- [x] 5.1 Implement `DocumentProfile` and deterministic profiling for Markdown levels, structural markers, page breaks, language hints, code/tables, and line statistics.
- [x] 5.2 Implement explicit character-size configuration and optional embedding token-limit enforcement without retaining legacy ambiguous setting aliases.
- [x] 5.3 Implement protected-span detection for fenced code, formulas, image/link references, and Markdown table header/rows with a configurable safety maximum.
- [x] 5.4 Implement priority-recursive separator splitting for paragraphs, lines, multilingual sentence punctuation, and final bounded hard splitting.
- [x] 5.5 Implement overlap alignment to structural/newline boundaries and table-header repetition without changing raw source offsets.
- [x] 5.6 Add recursive splitter tests for English/CJK prose, ordered separators, overlap, protected spans, large code/formulas, tables, offsets, and empty input.

## 6. Adaptive Strategies And Validation

- [x] 6.1 Implement heading hierarchy tracking, dominant-level selection, breadcrumb context, section splitting, deep-heading propagation, and tiny-section coalescing.
- [x] 6.2 Implement heuristic boundary detection and priority for page breaks, numbered sections, multilingual chapters, all-caps titles, visual separators, footers, and blank-line bursts.
- [x] 6.3 Exclude structural boundaries that fall inside protected spans and delegate oversized heading/heuristic regions to recursive splitting.
- [x] 6.4 Implement the automatic eligible-tier chain and explicit `heading`, `heuristic`, and `recursive` strategy selection.
- [x] 6.5 Implement full-output validation for empty, ineffective, tiny, uniformly undersized, and oversize results with recorded rejection reasons and recursive final fallback.
- [x] 6.6 Add profiler and strategy tests covering all eligibility thresholds, tier combinations, quality rejection, fallback trace, code-contained fake headings, and deterministic output.

## 7. Parent-Child And Structured Chunks

- [x] 7.1 Refactor `DocumentChunker` so parent generation and per-parent child generation both use the adaptive strategy with separate targets.
- [x] 7.2 Store context headers separately from raw content and build embedding/LLM context without duplicating headings or invalidating source offsets.
- [x] 7.3 Implement deterministic collapse for identical one-child parents and scoped parent recall/deduplication for retrieved children.
- [x] 7.4 Reconcile normalized table elements with protected table splitting and dedicated table chunks, including captions, headers, rows, nearby text, and parent links.
- [x] 7.5 Extend chunk models and repositories with strategy, processing version, size unit, image provenance, and `image_ocr`/`image_caption` types.
- [x] 7.6 Add tests for adaptive parent/child behavior, parent recall, collapse rules, breadcrumb embeddings, table chunks, stable provenance, and cross-KB retrieval isolation.

## 8. Index And Schema Integration

- [x] 8.1 Update SQLite document/chunk persistence and FTS indexing for the new provenance and indexable chunk types while keeping parent rows non-indexed.
- [x] 8.2 Update Milvus final schema, writes, filters, and retrieval metadata for processing version and `child`, `table`, `image_ocr`, and `image_caption` chunks.
- [x] 8.3 Update `RAGService` parse/index orchestration so parser, chunker, SQLite, FTS5, Milvus, parent recall, KG, and enrichment share one resolved KB scope and processing version.
- [x] 8.4 Implement schema incompatibility detection and `reset_required` maintenance behavior; normal startup and normal APIs MUST NOT delete legacy data automatically.
- [x] 8.5 Implement an explicit full-reset maintenance command that deletes the entire legacy SQLite database and all tables/data, every FTS table, all Milvus collections/vector data, legacy media, and all derived processing state before initializing the final empty schema.
- [x] 8.6 Add destructive-operation safeguards requiring explicit environment and deletion-scope confirmation, stopped-writer checks where practical, clear irreversible warnings, and post-reset empty-state verification.
- [x] 8.7 Add integration tests for full removal of authentication, tenant, KB, document, task, chat, memory, graph, evaluation, FTS, vector, and media data; schema mismatch; empty initialization; successful indexing; chunk replacement; deletion; and retrieval after reset.

## 9. Multimodal Operations

- [x] 9.1 Define OCR and VLM caption provider protocols, capability reporting, disabled providers, deterministic test fakes, and sanitized result/error models.
- [x] 9.2 Create durable scoped image operations after text parsing according to effective settings without blocking native text indexing.
- [x] 9.3 Implement bounded multimodal execution, per-image OCR/caption status, cancellation, targeted retry, and task-phase aggregation.
- [x] 9.4 Persist successful OCR and captions as separate evidence-bound chunks linked to image, page, document, KB, provider, confidence, and nearest text parent.
- [x] 9.5 Update deletion, reparse, and retry paths to avoid duplicate image chunks, and include every image resource and operation in the one-time full-reset path.
- [x] 9.6 Add tests proving provider failure isolation, independent retry, concurrency limits, generated-evidence labeling, parent/source recall, deduplication, and KB isolation.

## 10. Processing Preview And APIs

- [x] 10.1 Add read-only preview service execution that reuses production parser/profiler/chunker code with no repository, embedding, FTS, Milvus, KG, or enrichment writes.
- [x] 10.2 Add scoped preview request/response schemas for files and bounded samples, effective settings, diagnostics, profile, tier trace, full-set statistics, and bounded chunk previews.
- [x] 10.3 Enforce preview file/page/runtime/render/response limits, temporary resource cleanup, cancellation, and sanitized errors.
- [x] 10.4 Extend knowledge-base and staged-upload settings with parser engine, force-scanned, adaptive strategy, explicit size units, parent-child, OCR, and caption requested/effective fields.
- [x] 10.5 Extend durable batch/file task reporting with parse, chunk, index, multimodal, and postprocess phase status, warnings, errors, and retry eligibility.
- [x] 10.6 Add API tests proving preview has no side effects, fallback traces are returned, statistics cover all chunks, settings remain scoped, and unsupported capabilities are reported honestly.

## 11. Frontend Processing Controls

- [x] 11.1 Update frontend API types and clients for parser availability, adaptive chunk settings, PDF overrides, preview diagnostics, multimodal capability, and processing phase status.
- [x] 11.2 Update the knowledge-base/upload configuration UI to expose supported parser and chunking settings while disabling unavailable OCR/VLM options with effective-state explanations.
- [x] 11.3 Add a processing preview UI showing parser decision, PDF page classification counts, document profile, selected/rejected tiers, warnings, statistics, and bounded chunk cards.
- [x] 11.4 Update batch monitoring to distinguish text parse/index success from optional multimodal partial failure and offer only valid targeted retries.
- [x] 11.5 Add frontend tests for requested/effective configuration, unavailable engines, force-scanned controls, preview fallback, partial multimodal failure, and responsive layouts.

## 12. Documentation And Verification

- [x] 12.1 Update `docs/design-docs/backend-rag-pipeline.md` with registry resolution, hybrid PDF passes, adaptive tier chain, protected spans, parent-child indexing, multimodal phases, and the one-time full-database reset boundary.
- [x] 12.2 Update `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, README, environment examples, and API notes for parser dependencies, limits, preview, task phases, irreversible full-reset procedure, and the absence of legacy-data compatibility.
- [x] 12.3 Add safe non-corpus test fixtures and expected diagnostics for native, scanned, hybrid, structured Markdown, heuristic, unstructured, table, code, and CJK cases.
- [x] 12.4 Run focused backend parser/chunker/storage/task/API tests and the full backend suite using the documented environment.
- [x] 12.5 Run frontend tests, type checks, and production build.
- [x] 12.6 Run a manual scoped smoke test for preview, staged confirmation, mixed PDF processing, parent recall, optional OCR failure/retry, document preview, retrieval citations, and deletion cleanup.
- [x] 12.7 Run `openspec validate add-weknora-adaptive-document-processing --strict` and resolve all proposal, design, spec, and task inconsistencies.
