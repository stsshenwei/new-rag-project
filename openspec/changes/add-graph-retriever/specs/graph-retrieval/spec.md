## ADDED Requirements

### Requirement: Graph retrieval models
The system SHALL define structured graph retrieval result models for entities, relations, paths, source chunk ids, confidence, evidence chunks, and debug metadata.

#### Scenario: Return structured graph retrieval result
- **WHEN** GraphRetriever completes a retrieval method
- **THEN** it SHALL return structured fields for `entities`, `relations`, `paths`, `source_chunk_ids`, `confidence`, and optional `debug_info`.

#### Scenario: Preserve path evidence
- **WHEN** GraphRetriever returns a graph path
- **THEN** the path SHALL include all relation source chunk ids needed to trace the path back to raw evidence.

### Requirement: Graph query provider
The system SHALL expose a replaceable read-side graph query provider for entity lookup, neighbor traversal, and bounded path search.

#### Scenario: Query provider searches entities
- **WHEN** GraphRetriever needs entity candidates
- **THEN** it SHALL call a graph query provider method for entity name or alias lookup rather than embedding graph queries directly in orchestration code.

#### Scenario: Query provider searches neighbors
- **WHEN** GraphRetriever needs neighbors for an entity id
- **THEN** it SHALL call a graph query provider method for bounded neighbor traversal.

#### Scenario: Query provider searches paths
- **WHEN** GraphRetriever needs paths between two entities
- **THEN** it SHALL call a graph query provider method for bounded path search.

### Requirement: Entity search
The system SHALL support `entity_search(question)` to find candidate graph entities from entity names, aliases, and optional entity vector similarity.

#### Scenario: Find entity by name
- **WHEN** `entity_search(question)` receives text containing an entity name present in the graph
- **THEN** it SHALL return the matching entity with a confidence score.

#### Scenario: Find entity by alias
- **WHEN** `entity_search(question)` receives text containing an entity alias present in the graph
- **THEN** it SHALL return the canonical matching entity.

#### Scenario: Use optional entity vector search
- **WHEN** an entity vector provider is configured
- **THEN** `entity_search(question)` SHALL be able to include semantic entity matches without requiring graph traversal to fail if vector search is unavailable.

### Requirement: Neighbor search
The system SHALL support `neighbor_search(entity_id, depth)` to return nearby entities and evidence-bound relations.

#### Scenario: Find direct neighbors
- **WHEN** `neighbor_search(entity_id, depth=1)` is called for an entity with graph relations
- **THEN** it SHALL return adjacent entities, relations, source chunk ids, and confidence.

#### Scenario: Enforce neighbor depth cap
- **WHEN** `neighbor_search(entity_id, depth)` is called with a depth greater than the configured maximum
- **THEN** GraphRetriever SHALL cap the traversal depth before querying the graph provider.

#### Scenario: Filter unsupported relations
- **WHEN** neighbor search returns a relation type outside the allowed relation type list
- **THEN** GraphRetriever SHALL exclude that relation from the result.

### Requirement: Path search
The system SHALL support `path_search(source_entity, target_entity, max_depth)` to return bounded graph paths between two entities.

#### Scenario: Find path between entity ids
- **WHEN** `path_search(source_entity, target_entity, max_depth)` is called with two entity ids that have a graph path
- **THEN** GraphRetriever SHALL return one or more `GraphPath` results with entities, relations, source chunk ids, and confidence.

#### Scenario: Resolve entity names before path search
- **WHEN** `path_search(source_entity, target_entity, max_depth)` is called with entity names instead of ids
- **THEN** GraphRetriever SHALL resolve each name through entity search before requesting graph paths.

#### Scenario: Enforce path depth cap
- **WHEN** path search is called with `max_depth` greater than the configured maximum
- **THEN** GraphRetriever SHALL cap the path depth before querying the graph provider.

### Requirement: Source evidence validation
The system SHALL validate graph evidence against raw chunks before returning graph paths or relations as usable evidence.

#### Scenario: Relation includes source chunk
- **WHEN** GraphRetriever returns a relation
- **THEN** the relation SHALL include a non-empty `source_chunk_id`.

#### Scenario: Source chunk resolves to document chunk
- **WHEN** GraphRetriever returns a `source_chunk_id`
- **THEN** that chunk id SHALL resolve through `DocumentRepository.get_chunk()`.

#### Scenario: Exclude relation without source chunk
- **WHEN** the graph provider returns a relation without `source_chunk_id`
- **THEN** GraphRetriever SHALL exclude that relation from usable graph evidence.

#### Scenario: Exclude relation with missing raw chunk
- **WHEN** the graph provider returns a relation whose `source_chunk_id` does not resolve to `document_chunk`
- **THEN** GraphRetriever SHALL exclude that relation from usable graph evidence and expose the exclusion in debug metadata.

### Requirement: Graph context building
The system SHALL support `graph_context_build(paths, entities)` to convert graph retrieval results into structured context for later Agent tools.

#### Scenario: Build graph context from paths
- **WHEN** `graph_context_build(paths, entities)` receives valid graph paths
- **THEN** it SHALL return structured context containing readable path descriptions, involved entities, involved relations, source chunk ids, and evidence chunk metadata.

#### Scenario: Graph context does not generate answer
- **WHEN** graph context is built
- **THEN** GraphRetriever SHALL NOT generate a final natural-language answer.

### Requirement: Neo4j graph query implementation
The system SHALL provide a Neo4j read implementation for entity search, neighbor search, and path search while preserving optional Neo4j behavior.

#### Scenario: Backend starts when graph retrieval is not configured
- **WHEN** the Neo4j driver is not installed and graph retrieval is not configured
- **THEN** backend startup SHALL continue without requiring the Neo4j driver.

#### Scenario: Neo4j entity query uses allowed labels
- **WHEN** Neo4j entity search is executed
- **THEN** the query SHALL return only graph nodes whose entity type is in the allowed entity type list.

#### Scenario: Neo4j path query returns evidence properties
- **WHEN** Neo4j path search returns relationships
- **THEN** each returned relationship SHALL include `source_chunk_id`, `doc_id`, `page_start`, `page_end`, `extractor_version`, `confidence`, and `created_at` when present in the graph.

### Requirement: Default query compatibility
The system SHALL keep default Raw RAG query behavior unchanged by this change.

#### Scenario: RAG query does not call GraphRetriever by default
- **WHEN** `/rag/query` is called without a later Agentic retrieval change
- **THEN** the default answer path SHALL NOT call GraphRetriever.

#### Scenario: Chat stream remains graph independent
- **WHEN** `/chat/stream` is called without a later Agentic retrieval change
- **THEN** the stream SHALL preserve existing event behavior and SHALL NOT require graph retrieval.
