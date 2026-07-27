## ADDED Requirements

### Requirement: Low Recall Query Expansion
The document retrieval pipeline SHALL generate additional retrieval queries when initial dense/keyword recall is below configured minimum evidence thresholds.

#### Scenario: Initial recall is weak
- **WHEN** the first retrieval pass returns fewer than the configured minimum useful candidates
- **THEN** the system runs bounded query expansion and records the expanded queries in retrieval debug metadata

### Requirement: Rerank Threshold Degradation
The retrieval pipeline SHALL degrade rerank thresholds according to configuration when reranking filters out all useful candidates.

#### Scenario: Reranker filters all candidates
- **WHEN** rerank thresholding removes all candidates above the configured floor
- **THEN** the system retries selection with a lower threshold or bounded top candidate fallback and records the reason

### Requirement: MMR Diversity Selection
The retrieval pipeline SHALL support MMR-style diversity selection after fusion/rerank to reduce redundant evidence while preserving high-scoring candidates.

#### Scenario: Similar chunks dominate top results
- **WHEN** multiple candidates have near-duplicate content or shared parent context
- **THEN** the system selects a diverse subset according to configured relevance and diversity weights

### Requirement: Near-Duplicate Evidence Removal
The retrieval pipeline SHALL remove exact duplicates and near-duplicates using stable identifiers, content signatures, parent relationships, and overlap thresholds.

#### Scenario: Duplicate chunks appear from dense and keyword recall
- **WHEN** the same evidence is returned through multiple retrieval channels
- **THEN** the final context contains one canonical evidence item with merged trace metadata

### Requirement: Retrieval Debug Trace
The retrieval pipeline SHALL return or log structured debug metadata for query understanding, expansion, dense hits, keyword hits, fusion, rerank, threshold degradation, MMR, duplicate removal, parent recall, and context expansion.

#### Scenario: Debug retrieval requested
- **WHEN** a debug-enabled query is executed
- **THEN** the response includes a structured trace that explains candidate counts and decisions for each retrieval phase

