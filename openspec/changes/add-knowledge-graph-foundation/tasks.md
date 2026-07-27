## 1. KG Models And Contracts

- [x] 1.1 Add KG model types for `Entity`, `EntityMention`, `Relation`, `GraphPath`, and KG extraction result payloads.
- [x] 1.2 Add validation for allowed entity types and relation types.
- [x] 1.3 Require relation evidence fields: `source_chunk_id`, `doc_id`, `page_start`, `extractor_version`, `confidence`, and `created_at`.
- [x] 1.4 Add provider protocols for `KGExtractorProvider`, `EntityResolverProvider`, `EntityVectorProvider`, and `GraphStoreProvider`.

## 2. SQLite KG Repository

- [x] 2.1 Add idempotent SQLite schema for `kg_extraction_task`.
- [x] 2.2 Add idempotent SQLite schema for `entity_mention`.
- [x] 2.3 Add idempotent SQLite schema or repository placeholder for `graph_community_summary`.
- [x] 2.4 Add repository methods to create, update, complete, fail, and partial-fail KG extraction tasks.
- [x] 2.5 Add repository methods to insert and list entity mentions by document, entity, and chunk.
- [x] 2.6 Add tests for KG schema creation, task status transitions, mention persistence, and community summary placeholder storage.

## 3. KG Extractor Provider

- [x] 3.1 Add a KG extractor module with provider interface usage and extraction result validation.
- [x] 3.2 Add an OpenAI-compatible extractor implementation that accepts parent chunk content and returns structured entities and relations.
- [x] 3.3 Add malformed JSON and invalid entity/relation fallback behavior that fails the KG task without failing ingest.
- [x] 3.4 Add tests using fake extractor providers for successful extraction and extractor failures.

## 4. Entity Resolution

- [x] 4.1 Add baseline entity resolver with normalized exact name and entity type matching.
- [x] 4.2 Add alias-based matching for entities of the same type.
- [x] 4.3 Add entity vector similarity lookup hook through `EntityVectorProvider`.
- [x] 4.4 Add stable canonical entity id generation for new entities.
- [x] 4.5 Add tests for exact match, alias match, vector match hook, and new entity creation.

## 5. Entity Vector Store

- [x] 5.1 Add Milvus entity vector store for the `kg_entity_vectors` collection.
- [x] 5.2 Include fields for entity id, entity type, entity name, tenant id, knowledge base id, description, aliases, dense vector, and metadata.
- [x] 5.3 Add schema validation for existing `kg_entity_vectors` collections.
- [x] 5.4 Add tests for entity vector upsert, similarity search shape, and schema validation.

## 6. Neo4j Graph Store

- [x] 6.1 Add `Neo4jGraphStore` with lazy optional import of the Neo4j driver.
- [x] 6.2 Ensure backend startup does not require Neo4j when graph storage is disabled.
- [x] 6.3 Implement entity upsert using shared `Entity` label plus type label.
- [x] 6.4 Implement relation upsert with required evidence-bound properties.
- [x] 6.5 Add tests for optional import behavior, entity upsert Cypher shape, relation evidence properties, and graph write failure handling.

## 7. Ingest KG Enrichment Hook

- [x] 7.1 Add KG runtime configuration with `KG_EXTRACTION_ENABLED=false` by default.
- [x] 7.2 Add KG orchestration after parent chunks are stored and raw chunk/vector/FTS indexes are updated.
- [x] 7.3 Extract entities and relations from parent chunks only when KG extraction is enabled.
- [x] 7.4 Persist entity mentions to SQLite after entity resolution.
- [x] 7.5 Upsert canonical entities to the entity vector store and graph store when configured.
- [x] 7.6 Upsert evidence-bound relations to the graph store when configured.
- [x] 7.7 Mark KG tasks `completed`, `failed`, or `partial_failed` according to extraction, vector, and graph results.
- [x] 7.8 Add tests proving KG extraction failure does not fail document ingest or Raw RAG retrieval.

## 8. Query Behavior Compatibility

- [x] 8.1 Add tests proving `/rag/query` does not call graph retrieval by default.
- [x] 8.2 Add tests proving `/chat/stream` event behavior remains compatible.
- [x] 8.3 Ensure graph paths and used entities remain empty in default Raw RAG responses until a later GraphRetriever change.

## 9. Documentation And Validation

- [x] 9.1 Update `docs/ARCHITECTURE.md` with the KG foundation layer and optional provider boundaries.
- [x] 9.2 Update `docs/design-docs/backend-rag-pipeline.md` with the optional KG enrichment hook and failure isolation behavior.
- [x] 9.3 Update `docs/DEVELOPMENT.md` with KG environment variables, optional Neo4j notes, and validation commands.
- [x] 9.4 Run backend unit/API tests covering KG repository, extractor, resolver, entity vector store, Neo4j store, ingest hook, and query compatibility.
- [x] 9.5 Run a manual smoke test with KG disabled to verify existing ingest/query behavior remains unchanged.
- [x] 9.6 Run a fake-provider KG smoke test proving parent chunks can produce mentions, entity vectors, and graph writes without requiring a live Neo4j server.
