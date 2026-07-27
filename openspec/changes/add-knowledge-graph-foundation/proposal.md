## Why

The Raw Evidence Layer now provides traceable chunk evidence, but the system still lacks a durable knowledge graph foundation for entity and relation extraction. This change adds the KG data substrate needed for future GraphRetriever and Agent workflows without changing default RAG query behavior.

## What Changes

- Add SQLite persistence for KG extraction task tracking, entity mentions, and optional graph community summaries.
- Add KG model contracts for `Entity`, `EntityMention`, `Relation`, `GraphPath`, and extraction results.
- Add provider interfaces for graph storage, entity vectors, KG extraction, and entity resolution.
- Add a Neo4j graph store implementation with optional import so the backend can start when the Neo4j driver is not installed.
- Add a Milvus-backed entity vector store for the `kg_entity_vectors` collection.
- Add an optional, default-disabled KG enrichment hook after parent chunks are available during ingest.
- Ensure each graph relation is bound to raw evidence metadata: `source_chunk_id`, `doc_id`, `page_start`, `extractor_version`, `confidence`, and `created_at`.
- Record KG extraction failures as failed or partial-failed KG tasks without failing document ingest or Raw RAG indexing.

## Capabilities

### New Capabilities

- `knowledge-graph-foundation`: KG task tracking, entity mention persistence, KG model/provider contracts, optional Neo4j graph writes, entity vector indexing, and failure-isolated KG extraction during ingest.

### Modified Capabilities

- None.

## Impact

- Backend models: new KG dataclasses or Pydantic models for entities, mentions, relations, paths, and extraction results.
- Backend services: new repository, extractor, resolver, graph store, and entity vector store modules.
- Backend configuration: new KG-related environment flags, with KG extraction disabled by default.
- Backend dependencies: Neo4j support must be optional; missing Neo4j driver must not break backend startup.
- Ingest pipeline: parent chunks may trigger KG extraction when enabled, but Raw RAG ingest remains the primary success path.
- Storage: SQLite metadata DB gains KG tables; Milvus gains optional `kg_entity_vectors`; Neo4j receives entity and relation writes when configured.
- APIs: `/rag/query` and `/chat/stream` do not use graph retrieval by default in this change.
- No frontend graph UI, complex path retrieval, QueryRouter, or Agent workflow is included.
