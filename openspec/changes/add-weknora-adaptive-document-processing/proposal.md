## Why

The current ingestion pipeline is intended to use Docling, but its PDF/DOCX control flow is incomplete and the chunker still relies on fixed H1/H2 grouping plus character slicing. This prevents reliable handling of hybrid PDFs, scanned pages, document structure, and retrieval-oriented parent-child chunking.

This change adapts the proven WeKnora processing shape to the existing FastAPI, SQLite, FTS5, and Milvus architecture: a built-in parser registry, per-page hybrid PDF routing, adaptive structure-aware chunking, and independently recoverable multimodal post-processing.

## What Changes

- Add a parser-engine registry with a default `builtin` engine and explicit requested/effective engine reporting, while retaining Docling as an optional engine or fallback rather than the only parser path.
- Add built-in parsers for the project's supported document formats, led by a `pypdfium2` hybrid PDF parser that classifies every page as native-text or scanned.
- Parse hybrid PDFs in ordered passes: extract and reconstruct native text pages, render only scanned pages, extract embedded/vector figures, then assemble Markdown and image references in page order.
- Add structured parse diagnostics, stable page/image provenance, controlled fallback behavior, and explicit parse error codes.
- Add adaptive `auto`, `heading`, `heuristic`, and `recursive` chunking with document profiling, protected spans, output validation, and deterministic fallback.
- Rework parent-child chunking so parent and child levels both use the adaptive strategy while only retrieval chunks are indexed.
- Add independent image OCR and VLM-caption processing that creates evidence-bound `image_ocr` and `image_caption` chunks without making text parsing depend on provider success.
- Add a read-only processing preview that reports parser decisions, document profile, chosen/rejected chunking tiers, chunk statistics, and warnings without writing embeddings or corpus state.
- Extend staged upload settings and task status so parsing, chunking, indexing, multimodal work, and post-processing are observable and retryable within one knowledge-base scope.
- **BREAKING** for all persisted application data: activation of the new processing architecture requires a one-time full reset that deletes the entire legacy SQLite database, every FTS table, all Milvus collections/vector data, and legacy media/derived processing data. No legacy authentication, tenant, knowledge-base, document, task, chat, memory, graph, evaluation, or index records are retained or exposed.

## Capabilities

### New Capabilities

- `parser-engine-registry`: Format-aware parser selection, built-in fallback, availability reporting, and requested/effective parser provenance.
- `hybrid-pdf-parsing`: Per-page native/scanned PDF routing, layout-aware Markdown reconstruction, selective rendering, image extraction, diagnostics, and safe fallback.
- `adaptive-document-chunking`: Document profiling, heading/heuristic/recursive strategy selection, protected spans, validation fallback, and adaptive parent-child chunks.
- `multimodal-document-processing`: Durable image resources, independently scheduled OCR/VLM processing, evidence-bound image chunks, failure isolation, and retry.
- `document-processing-preview`: Read-only parser and chunker preview with structural profile, strategy trace, statistics, and no indexing side effects.

### Modified Capabilities

- None. No main specifications have been archived under `openspec/specs/`; integration with staged uploads and processing tasks is defined as part of the new capability contracts.

## Impact

- Backend models and services: `document_parser.py`, `document_chunker.py`, `document_loader.py`, `rag_service.py`, document/task repositories, schemas, and processing routes.
- Storage: SQLite document/chunk/image/task metadata, local object-storage provider initially, FTS5 derived rows, and Milvus chunk metadata/schema.
- Dependencies: add `pypdfium2` and format-specific parser libraries where not already present; OCR and VLM remain provider interfaces and optional runtime capabilities.
- API/UI: knowledge-base and upload-batch parser/chunker settings, processing preview responses, effective configuration, warnings, task phase status, and retry behavior.
- Operations: bounded PDF rendering and multimodal concurrency, file/page/resource limits, structured failure codes, and an explicit one-time full-database reset before the new application schema is initialized.
- Documentation and tests: update backend pipeline architecture, environment/configuration references, parser/chunker behavior, and mixed/native/scanned PDF fixtures.
