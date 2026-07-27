## ADDED Requirements

### Requirement: Immutable Chunking Fallback Chain
The adaptive chunking strategy SHALL preserve the Weknora fallback invariant: auto may select heading, then heuristic, and must always end with legacy; explicit heading and heuristic must fall back to legacy; recursive and legacy must remain legacy-only.

#### Scenario: Auto heading document
- **WHEN** auto strategy profiles a document with sufficient Markdown heading structure
- **THEN** the attempted strategy chain starts with heading and ends with legacy

#### Scenario: Explicit heuristic document
- **WHEN** heuristic strategy is explicitly selected
- **THEN** the attempted strategy chain is heuristic followed by legacy

#### Scenario: Legacy document
- **WHEN** legacy or recursive strategy is selected
- **THEN** the strategy chain contains only legacy

### Requirement: Chunking Rejection Diagnostics
The chunker SHALL record selected tier, attempted tiers, rejected tiers, profile signals, and validation rejection reasons.

#### Scenario: Heading output rejected
- **WHEN** heading chunking produces invalid output
- **THEN** diagnostics record the heading rejection reason and the fallback tier that was selected

### Requirement: Chinese And Protected-Region Parity Fixtures
The chunking test suite SHALL include fixtures for Chinese punctuation, Chinese chapter markers, Markdown headings, heuristic markers, fenced code, formulas, image references, tables, and long protected regions.

#### Scenario: Chinese chapter document
- **WHEN** a Chinese chapter-structured document is chunked
- **THEN** profiling detects Chinese chapter markers and chunking diagnostics remain UTF-8 readable

### Requirement: Parent-Child Chunking Guardrails
Parent-child chunking SHALL preserve deterministic parent/child relationships, context headers, source offsets where available, and collapse rules for redundant identical parent-child evidence.

#### Scenario: Single identical child
- **WHEN** a parent chunk produces exactly one child with identical content
- **THEN** the system applies the configured collapse rule and avoids duplicate retrievable evidence

