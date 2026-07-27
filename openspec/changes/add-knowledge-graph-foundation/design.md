## Context

The current backend has a completed Raw Evidence Layer: documents are parsed into parent/child/table/OCR chunks, persisted in SQLite, indexed into Milvus for vectors, indexed into SQLite FTS5 for exact keyword recall, and exposed through traceable citations. The next architectural step is to enrich parent chunks into a knowledge graph substrate.

This change does not make the graph part of default answering. It creates the data and provider foundation needed for later GraphRetriever and Agent workflow changes. KG extraction must be optional, default-disabled, and failure-isolated so existing Raw RAG ingest remains dependable.

## Goals / Non-Goals

**Goals:**

- Add SQLite tables for KG extraction tasks, entity mentions, and graph community summary placeholders.
- Add KG model contracts for entities, mentions, relations, graph paths, and extraction results.
- Add provider interfaces for KG extraction, entity resolution, entity vector storage, and graph storage.
- Add an optional Neo4j graph store implementation with optional import behavior.
- Add a Milvus-backed entity vector store for `kg_entity_vectors`.
- Add a default-disabled KG enrichment hook after parent chunks are available in ingest.
- Ensure every graph relation is bound to raw evidence metadata: `source_chunk_id`, `doc_id`, `page_start`, `extractor_version`, `confidence`, and `created_at`.
- Ensure KG extraction failures mark KG task status but do not fail Raw RAG ingest.

**Non-Goals:**

- Do not make `/rag/query` or `/chat/stream` use graph retrieval by default.
- Do not implement GraphRetriever, neighbor search, path search, or complex graph reasoning.
- Do not build a frontend graph viewer.
- Do not add QueryRouter, RetrievalPlanner, or Agent workflow behavior.
- Do not require Neo4j or the Neo4j Python driver for backend startup.
- Do not enable KG extraction by default.

## Decisions

### Decision 1: Treat KG enrichment as best-effort ingest enrichment

KG extraction runs after raw chunks are persisted and indexed. If KG extraction fails, the document remains parsed and searchable by Raw RAG. The KG task records `failed` or `partial_failed` status with an error message.

Rationale: Raw RAG is the primary data path. KG enrichment is useful but more expensive and more operationally fragile because it can depend on LLM extraction, entity vector indexing, Milvus entity collection schema, and Neo4j availability.

Alternative considered: make KG extraction part of ingest success. This was rejected because a graph outage or extraction error would block document search.

### Decision 2: Keep KG extraction disabled by default

Add a runtime flag such as `KG_EXTRACTION_ENABLED=false`. When disabled, ingest behaves exactly like Raw RAG and does not create KG extraction tasks.

Rationale: KG extraction can add cost, latency, and infrastructure dependencies. It should be enabled deliberately after local validation.

Alternative considered: enable KG extraction automatically after this change. That was rejected because the user explicitly wants the foundation without immediately changing default behavior.

### Decision 3: Store entity mentions in SQLite and graph entities/relations in providers

SQLite owns task tracking and mention provenance. Neo4j owns graph topology. Milvus owns entity semantic vectors. This mirrors the Raw Evidence Layer split where SQLite owns metadata and Milvus owns vector search.

Rationale: Mention rows need to be queryable and auditable with source chunks even if Neo4j is unavailable. Graph traversal belongs in Neo4j, and entity similarity belongs in Milvus.

Alternative considered: put all KG state in Neo4j. That was rejected because extraction task status and mention provenance should remain available in the existing metadata store.

### Decision 4: Use provider interfaces before concrete implementations

Define:

- `KGExtractorProvider`
- `EntityResolverProvider`
- `EntityVectorProvider`
- `GraphStoreProvider`

Concrete implementations can include an OpenAI-compatible KG extractor, a baseline resolver, a Milvus entity vector store, and a Neo4j graph store.

Rationale: The project already uses provider boundaries for embeddings, reranking, retrieval, and raw evidence. KG providers keep future swaps possible without rewriting ingest orchestration.

Alternative considered: implement only concrete classes first. This was rejected because KG infrastructure is explicitly expected to be replaceable.

### Decision 5: Make Neo4j optional with lazy imports

`Neo4jGraphStore` imports the Neo4j driver inside the implementation path, not at module import time. If the driver is missing and graph storage is disabled, backend startup still succeeds. If graph storage is enabled without the driver, the KG task fails with a clear error while Raw RAG ingest still succeeds.

Rationale: The user confirmed optional import behavior. Local development and tests must not require Neo4j.

Alternative considered: add `neo4j` to required dependencies immediately. That was rejected because it makes a disabled optional feature affect baseline startup.

### Decision 6: Use typed entity labels with a shared base graph label

Neo4j nodes should be written with both a shared label and a type label, for example `(:Entity:Service)` or `(:Entity:API)`. The model still exposes a single `entity_type` field from the allowed type vocabulary.

Rationale: A shared label simplifies generic graph operations while type labels keep domain queries efficient and readable.

Alternative considered: create only type-specific labels. That was rejected because cross-type entity queries become awkward.

### Decision 7: Require relation evidence binding

Every `Relation` written to the graph must carry `source_chunk_id`, `doc_id`, `page_start`, `extractor_version`, `confidence`, and `created_at`.

Rationale: Future GraphRetriever and CitationVerifier need to prove each graph edge came from raw evidence. Relations without source evidence should not enter the graph.

Alternative considered: allow relations without evidence and backfill later. That was rejected because graph trust is much harder to restore after unsupported edges exist.

## Risks / Trade-offs

- KG extraction increases ingest latency -> Keep `KG_EXTRACTION_ENABLED=false` by default and process KG enrichment only when explicitly enabled.
- LLM extraction may produce malformed JSON -> Validate extractor output and mark task failure without failing Raw RAG.
- Entity resolution can merge incorrectly -> Start with conservative exact name, alias, and vector matching; keep optional LLM same-entity judgment behind provider/config.
- Neo4j driver or server may be missing -> Use optional import, lazy connection, and task-level failure isolation.
- Milvus entity collection schema can drift -> Validate `kg_entity_vectors` schema and fail KG task clearly when incompatible.
- Duplicate entity mentions can grow quickly -> Use stable mention IDs or unique constraints by entity/chunk/mention text where practical.

## Migration Plan

1. Add KG models and provider protocols.
2. Add SQLite KG repository tables and idempotent schema initialization.
3. Add baseline extractor result validation and fake/test extractor support.
4. Add conservative entity resolver with exact and alias matching, plus entity vector lookup hooks.
5. Add Milvus entity vector store for `kg_entity_vectors`.
6. Add `Neo4jGraphStore` with optional import and evidence-bound relation writes.
7. Add KG enrichment orchestration behind `KG_EXTRACTION_ENABLED=false`.
8. Add tests proving parent chunks can produce entities/relations, mentions are persisted, entities can be resolved/merged, relations can be written through the graph provider, and KG failures do not fail Raw RAG ingest.
9. Update architecture and backend RAG pipeline docs.

Rollback is simple: set `KG_EXTRACTION_ENABLED=false`. Existing raw evidence data remains valid; KG tables and graph data are derived enrichment state.

## Open Questions

- Should entity resolution use LLM same-entity judgment in the first implementation, or keep LLM judgment as an interface-only hook? Recommended: interface hook only, with exact/alias/vector baseline first.
- Should `graph_community_summary` be fully functional now or only schema/repository placeholders? Recommended: schema and repository placeholders only.
- Should KG extraction run synchronously during ingest or be task-queued later? Recommended: synchronous best-effort hook for this foundation change, with task status records preparing for async later.
