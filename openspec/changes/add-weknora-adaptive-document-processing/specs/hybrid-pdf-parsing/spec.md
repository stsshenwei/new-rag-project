## ADDED Requirements

### Requirement: Per-page hybrid PDF routing
The builtin PDF parser SHALL use `pypdfium2` to classify each page independently as native text or scanned using text availability and image-area signals.

#### Scenario: Mixed PDF
- **WHEN** a PDF contains both native-text pages and scanned pages
- **THEN** native pages SHALL contribute reconstructed text while only scanned pages SHALL be rendered as images, preserving original page order

#### Scenario: Force-scanned mode
- **WHEN** effective upload settings enable force-scanned parsing
- **THEN** every page SHALL be rendered and no native text-layer content SHALL be trusted

### Requirement: Native page Markdown reconstruction
The parser SHALL reconstruct readable text order for malformed native extraction where layout data is better, promote defensible visual headings to Markdown headings, and remove detected repeating headers or footers without discarding ordinary body text.

#### Scenario: Usable plain text layer
- **WHEN** plain extraction passes quality checks
- **THEN** the parser SHALL prefer it over more expensive layout reconstruction

#### Scenario: Broken plain reading order
- **WHEN** plain extraction fails quality checks and layout extraction produces better content
- **THEN** the parser SHALL use layout-aware order and retain page provenance

### Requirement: Selective scanned-page rendering
Scanned pages SHALL be rendered to bounded JPEG resources using configurable DPI, quality, edge limits, and concurrency.

#### Scenario: Large scanned document
- **WHEN** many scanned pages require rendering
- **THEN** rendering SHALL obey its dedicated concurrency budget and SHALL NOT use unbounded workers

#### Scenario: Routing failure eligible for safe fallback
- **WHEN** per-page routing fails unexpectedly and the document is otherwise renderable
- **THEN** the parser SHALL fall back to full-page rendering and record that fallback

### Requirement: Figure extraction and ordered assembly
The parser SHALL extract eligible embedded images and vector-figure clips from native pages, filter trivial assets, and assemble Markdown text and image references in source page order.

#### Scenario: Native page with embedded figure
- **WHEN** an eligible figure is found on a native page
- **THEN** the result SHALL include a stable image resource with page provenance and a Markdown reference associated with that page

### Requirement: Structured PDF diagnostics
PDF results SHALL expose page counts, native/scanned counts, embedded-image and vector-figure counts, source classification, warnings, and stable failure codes.

#### Scenario: Successful hybrid parse
- **WHEN** hybrid parsing completes
- **THEN** the reported native and scanned page counts SHALL sum to the total page count

#### Scenario: Password-protected PDF
- **WHEN** the PDF requires a password that was not supplied
- **THEN** parsing SHALL fail explicitly and SHALL NOT silently enter a render-all retry loop

