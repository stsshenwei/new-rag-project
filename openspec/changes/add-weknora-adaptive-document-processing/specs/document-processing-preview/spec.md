## ADDED Requirements

### Requirement: Read-only processing preview
The backend SHALL provide a scoped preview that runs parser and chunker decisions without embeddings, vector writes, FTS writes, document publication, enrichment, or corpus mutation.

#### Scenario: Preview sample
- **WHEN** a user previews a supported file or bounded sample with valid settings
- **THEN** the backend SHALL return parse and chunk results without changing retrievable knowledge

### Requirement: Preview decision trace
Preview output SHALL report requested/effective parser, parse diagnostics, document profile, selected strategy, rejected strategies and reasons, effective settings, warnings, and chunk counts by type.

#### Scenario: Strategy fallback visible
- **WHEN** a structural tier is rejected and a lower tier succeeds
- **THEN** the preview SHALL identify both the rejected tier reason and final selected tier

### Requirement: Preview statistics and provenance
Preview SHALL calculate statistics over the full produced chunk set and return bounded per-chunk content previews with size, approximate token count, parent, title path, page, and strategy provenance.

#### Scenario: Full-set statistics
- **WHEN** a preview produces multiple chunks
- **THEN** minimum, maximum, average, dispersion, and tiny/oversize counts SHALL reflect the complete chunk set rather than only displayed samples

### Requirement: Preview limits and safety
Preview SHALL enforce input size, page, runtime, image-render, and returned-content limits and SHALL sanitize parser errors.

#### Scenario: Preview timeout
- **WHEN** preview exceeds its configured runtime budget
- **THEN** it SHALL terminate with a structured timeout response and SHALL leave no durable processing state

