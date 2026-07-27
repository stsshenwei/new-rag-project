## ADDED Requirements

### Requirement: Durable parsed image resources
Parsed scanned pages, embedded images, and vector figures SHALL be stored through an object-storage provider and SHALL retain document, page, source-type, media, and parent-element provenance.

#### Scenario: Local provider
- **WHEN** no remote object store is configured
- **THEN** the system SHALL use a path-safe local provider without storing large image payloads in SQLite

### Requirement: Independent OCR and caption processing
OCR and VLM caption work SHALL execute after text parsing as independently observable operations and SHALL NOT be required for successful native text indexing.

#### Scenario: OCR provider failure
- **WHEN** OCR fails for one scanned page
- **THEN** native text chunks and other successful image chunks SHALL remain available and the failed image operation SHALL be retryable

#### Scenario: Multimodal capability disabled
- **WHEN** OCR or caption capability is disabled or unavailable
- **THEN** the system SHALL report the effective disabled state and SHALL NOT imply that image understanding occurred

### Requirement: Evidence-bound image chunks
Successful OCR and VLM results SHALL create separate `image_ocr` and `image_caption` chunks linked to their image resource, page, document, knowledge base, and nearest applicable text parent.

#### Scenario: Image chunk retrieval
- **WHEN** an image-derived chunk is retrieved
- **THEN** the system SHALL be able to return its source image and parent text evidence without merging generated text into the original parent body

### Requirement: Isolated multimodal concurrency and retry
Multimodal work SHALL use bounded concurrency independent from document parsing and SHALL permit targeted retry without reparsing or reindexing unaffected text.

#### Scenario: Large scanned PDF
- **WHEN** a document produces many image operations
- **THEN** those operations SHALL NOT monopolize the parsing worker budget or duplicate successful text chunks

### Requirement: Knowledge-base scope preservation
Every image resource, operation, derived chunk, lookup, delete, and retry SHALL remain bound to exactly one workspace and knowledge base.

#### Scenario: Cross-KB image access
- **WHEN** a client requests an image or retry using a different knowledge-base scope
- **THEN** the backend SHALL reject or hide the resource without revealing its metadata

