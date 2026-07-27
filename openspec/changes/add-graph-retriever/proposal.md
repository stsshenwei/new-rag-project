## Why

The knowledge graph foundation can write entities and evidence-bound relations, but the system still lacks a read-side graph retrieval tool that an Agent can call. This change turns graph data into structured, traceable evidence without changing the default Raw RAG answer path.

## What Changes

- Add a `GraphRetriever` service that exposes entity search, neighbor search, path search, and graph context building.
- Add read-side graph provider contracts so graph traversal remains replaceable and not tied directly to Neo4j call sites.
- Extend the Neo4j graph store with read queries for entity lookup, neighbor traversal, and bounded path search.
- Validate returned node types and relationship types against the existing KG allowlists.
- Require every returned graph relation and path edge to include `source_chunk_id` and enough metadata to trace back to raw evidence.
- Use `DocumentRepository` to verify graph source chunks can be resolved from `document_chunk`.
- Return structured graph evidence only: entities, relations, paths, source chunk ids, confidence, and optional evidence chunk data.
- Keep `/rag/query` and `/chat/stream` on Raw RAG by default; this change does not implement Agent FSM or final answer generation from graph evidence.

## Capabilities

### New Capabilities

- `graph-retrieval`: Read-only graph retrieval for entity search, neighbor search, path search, and traceable graph context building.

### Modified Capabilities

- None.

## Impact

- Backend models: new graph retrieval result structures for entities, relations, paths, source chunk ids, confidence, and debug metadata.
- Backend services: new `GraphRetriever` service and read-side graph query provider protocol.
- Graph provider: `Neo4jGraphStore` gains read methods while preserving optional import behavior.
- Raw evidence integration: graph path edges are validated against SQLite `document_chunk` through `DocumentRepository`.
- Tests: fake graph provider tests plus Neo4j query-shape tests for entity, neighbor, and path retrieval.
- APIs: no default behavior change for `/rag/query` or `/chat/stream`; graph retrieval is a backend tool for a later Agent workflow.
