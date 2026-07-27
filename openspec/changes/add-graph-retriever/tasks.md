## 1. Graph Retrieval Models And Contracts

- [x] 1.1 Add graph retrieval result models for entities, relations, paths, source chunk ids, confidence, evidence chunks, and debug metadata.
- [x] 1.2 Add a `GraphQueryProvider` protocol with methods for entity search, neighbor search, and path search.
- [x] 1.3 Reuse existing KG entity and relation type allowlists for graph retrieval validation.
- [x] 1.4 Add tests for graph retrieval model serialization and invalid type filtering expectations.

## 2. Neo4j Read-Side Provider

- [x] 2.1 Extend `Neo4jGraphStore` to search entities by id, name, and alias.
- [x] 2.2 Extend `Neo4jGraphStore` to return bounded neighbors with entities and evidence-bound relations.
- [x] 2.3 Extend `Neo4jGraphStore` to return bounded paths with entities and evidence-bound relations.
- [x] 2.4 Preserve lazy optional Neo4j import behavior for read-side graph retrieval.
- [x] 2.5 Add tests for Neo4j entity, neighbor, and path query shapes.

## 3. GraphRetriever Service

- [x] 3.1 Add a `GraphRetriever` service that accepts a `GraphQueryProvider`, `DocumentRepository`, and optional `EntityVectorProvider`.
- [x] 3.2 Implement `entity_search(question)` using graph lookup and optional entity vector lookup.
- [x] 3.3 Implement `neighbor_search(entity_id, depth)` with configurable default and maximum depth.
- [x] 3.4 Implement `path_search(source_entity, target_entity, max_depth)` with id/name resolution and configurable maximum depth.
- [x] 3.5 Implement `graph_context_build(paths, entities)` returning structured context without final answer generation.

## 4. Evidence Validation

- [x] 4.1 Validate every returned relation has non-empty `source_chunk_id`.
- [x] 4.2 Resolve every returned `source_chunk_id` through `DocumentRepository.get_chunk()`.
- [x] 4.3 Exclude relations and paths whose source chunks are missing or invalid.
- [x] 4.4 Preserve debug metadata for excluded relations and missing chunks.
- [x] 4.5 Add tests proving graph paths can be traced back to `document_chunk`.

## 5. Confidence And Result Shaping

- [x] 5.1 Calculate confidence from entity match scores, relation confidence, and source validation status.
- [x] 5.2 Deduplicate entities, relations, and source chunk ids across retrieved paths.
- [x] 5.3 Enforce result limits for entity candidates, neighbors, paths, and evidence chunks.
- [x] 5.4 Add tests for confidence calculation, deduplication, and traversal caps.

## 6. Query Compatibility And Runtime Wiring

- [x] 6.1 Add runtime configuration for optional GraphRetriever construction without requiring Neo4j when disabled.
- [x] 6.2 Ensure `/rag/query` does not call GraphRetriever by default.
- [x] 6.3 Ensure `/chat/stream` does not require GraphRetriever and preserves existing SSE behavior.
- [x] 6.4 Add tests for graph retrieval disabled startup and default Raw RAG compatibility.

## 7. Documentation And Validation

- [x] 7.1 Update `docs/ARCHITECTURE.md` with GraphRetriever as an Agent-callable graph evidence tool.
- [x] 7.2 Update `docs/design-docs/backend-rag-pipeline.md` to clarify that GraphRetriever is read-only and not part of default Raw RAG.
- [x] 7.3 Update `docs/DEVELOPMENT.md` with GraphRetriever configuration and validation commands.
- [x] 7.4 Run backend unit/API tests covering graph models, Neo4j read provider, GraphRetriever, evidence validation, and Raw RAG compatibility.
- [x] 7.5 Run a fake-provider smoke test proving entity search, neighbor search, path search, and source chunk validation work without live Neo4j.
