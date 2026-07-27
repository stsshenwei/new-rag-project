## ADDED Requirements

### Requirement: KG extraction task tracking
The system SHALL persist KG extraction task status independently from raw document parse and Raw RAG ingest status.

#### Scenario: Create task when KG extraction is enabled
- **WHEN** KG extraction is enabled and a document has parent chunks available after ingest
- **THEN** the system SHALL create a `kg_extraction_task` record containing task id, document id, status, timestamps, extractor version, and task metadata.

#### Scenario: Skip task when KG extraction is disabled
- **WHEN** KG extraction is disabled
- **THEN** document ingest SHALL NOT create KG extraction tasks and SHALL preserve existing Raw RAG ingest behavior.

#### Scenario: Record extraction failure
- **WHEN** KG extraction fails for a document or a subset of parent chunks
- **THEN** the system SHALL mark the KG extraction task as `failed` or `partial_failed` with an error message and SHALL NOT fail Raw RAG ingest.

### Requirement: Entity mention persistence
The system SHALL persist entity mentions extracted from raw parent chunks in SQLite.

#### Scenario: Store entity mention
- **WHEN** an entity is extracted from a parent chunk
- **THEN** the system SHALL store an `entity_mention` row with id, entity id, entity type, entity name, document id, chunk id, parent id, page range, mention text, confidence, and created timestamp.

#### Scenario: Preserve mention provenance
- **WHEN** an entity mention is stored
- **THEN** the mention SHALL remain traceable to the raw evidence chunk through `doc_id`, `chunk_id`, and `parent_id`.

### Requirement: Graph community summary placeholder
The system SHALL provide a durable placeholder table or repository boundary for future graph community summaries.

#### Scenario: Initialize community summary storage
- **WHEN** the KG repository initializes
- **THEN** it SHALL create storage for `graph_community_summary` records without requiring summary generation in this change.

### Requirement: KG model contracts
The system SHALL define typed KG model contracts for entities, entity mentions, relations, graph paths, and extraction results.

#### Scenario: Entity model fields
- **WHEN** the system represents an entity
- **THEN** the entity model SHALL include id, type, name, description, aliases, confidence, and metadata.

#### Scenario: Relation evidence fields
- **WHEN** the system represents a relation
- **THEN** the relation model SHALL include source entity id, target entity id, relation type, description, confidence, source chunk id, document id, page start, extractor version, created timestamp, and metadata.

#### Scenario: Graph path model fields
- **WHEN** the system represents a graph path
- **THEN** the graph path model SHALL include entities, relations, source chunk ids, and confidence.

### Requirement: KG provider interfaces
The system SHALL expose replaceable provider interfaces for KG extraction, entity resolution, entity vector storage, and graph storage.

#### Scenario: Extractor provider
- **WHEN** KG extraction is requested for a parent chunk
- **THEN** the system SHALL call a `KGExtractorProvider` contract that returns validated entities and relations.

#### Scenario: Resolver provider
- **WHEN** extracted entities need canonical entity ids
- **THEN** the system SHALL call an `EntityResolverProvider` contract that can resolve or merge entities.

#### Scenario: Entity vector provider
- **WHEN** canonical entities need semantic indexing
- **THEN** the system SHALL call an `EntityVectorProvider` contract for upsert and similarity lookup.

#### Scenario: Graph store provider
- **WHEN** canonical entities and relations need graph persistence
- **THEN** the system SHALL call a `GraphStoreProvider` contract rather than writing graph queries from ingest orchestration.

### Requirement: Optional Neo4j graph store
The system SHALL provide a Neo4j graph store implementation that does not break backend startup when the Neo4j driver is missing.

#### Scenario: Missing Neo4j driver while graph disabled
- **WHEN** the Neo4j Python driver is not installed and KG graph storage is disabled
- **THEN** backend startup SHALL continue without importing or requiring the Neo4j driver.

#### Scenario: Missing Neo4j driver while graph enabled
- **WHEN** KG graph storage is enabled but the Neo4j Python driver is not installed
- **THEN** KG extraction SHALL fail the KG task with a clear error and SHALL NOT fail Raw RAG ingest.

#### Scenario: Write evidence-bound relation
- **WHEN** a relation is written to Neo4j
- **THEN** the relationship properties SHALL include confidence, source chunk id, document id, page start, extractor version, and created timestamp.

### Requirement: Entity vector collection
The system SHALL support a Milvus `kg_entity_vectors` collection for entity semantic indexing.

#### Scenario: Upsert entity vector
- **WHEN** a canonical entity is resolved
- **THEN** the system SHALL be able to upsert an entity vector row containing entity id, entity type, entity name, tenant id, knowledge base id, description, aliases, dense vector, and metadata.

#### Scenario: Similarity lookup for resolution
- **WHEN** entity resolution requires embedding similarity
- **THEN** the entity vector provider SHALL support similarity lookup by entity description or embedding text.

### Requirement: Conservative entity resolution
The system SHALL provide a baseline entity resolver that can resolve entities by exact name, aliases, and optional vector similarity.

#### Scenario: Exact name match
- **WHEN** an extracted entity has the same normalized name and type as an existing canonical entity
- **THEN** the resolver SHALL return the existing canonical entity id.

#### Scenario: Alias match
- **WHEN** an extracted entity matches an existing entity alias within the same type
- **THEN** the resolver SHALL return the existing canonical entity id.

#### Scenario: New entity creation
- **WHEN** no exact, alias, or configured vector match is found
- **THEN** the resolver SHALL create or return a new canonical entity id.

### Requirement: KG extraction from parent chunks
The system SHALL support optional KG extraction from parent chunks after raw chunks are stored.

#### Scenario: Extract entities and relations from parent chunk
- **WHEN** KG extraction is enabled and a parent chunk is processed
- **THEN** the system SHALL pass parent chunk content, document id, parent id, chunk id, title path, and page range to the KG extractor.

#### Scenario: Bind relation to raw source
- **WHEN** a relation is produced from a parent chunk
- **THEN** the system SHALL bind the relation to source chunk id, document id, page start, page end when available, extractor version, confidence, and created timestamp before graph persistence.

### Requirement: No default graph query behavior
The system SHALL NOT use the knowledge graph in default query answering as part of this foundation change.

#### Scenario: Query remains raw evidence based
- **WHEN** `/rag/query` is called after this change
- **THEN** the default answer path SHALL continue to use Raw RAG retrieval and SHALL NOT call GraphRetriever or graph path search.

#### Scenario: Chat stream remains compatible
- **WHEN** `/chat/stream` is called after this change
- **THEN** existing chat stream events and answer behavior SHALL remain compatible and SHALL NOT require graph retrieval.

### Requirement: KG failure isolation
The system SHALL isolate KG extraction, entity vector, and graph write failures from Raw RAG ingest.

#### Scenario: Extractor failure
- **WHEN** the KG extractor raises an error for a parent chunk
- **THEN** the KG task SHALL record failure information and the document SHALL remain searchable through Raw RAG.

#### Scenario: Entity vector failure
- **WHEN** entity vector upsert fails during KG enrichment
- **THEN** the KG task SHALL record failure or partial failure and the document SHALL remain searchable through Raw RAG.

#### Scenario: Graph write failure
- **WHEN** Neo4j relation or entity writes fail during KG enrichment
- **THEN** the KG task SHALL record failure or partial failure and the document SHALL remain searchable through Raw RAG.
