## Context

The Raw Evidence Layer can store and retrieve source chunks through SQLite, Milvus, and FTS5. The KG foundation can extract parent-chunk entities and relations, persist mentions in SQLite, write entity vectors to Milvus, and write evidence-bound entities and relations to Neo4j.

The missing piece is the read-side graph retrieval tool. Future Agent workflow changes need a deterministic tool that can search graph entities, traverse neighbors, find bounded paths, and return graph evidence that is traceable back to `document_chunk`. This change introduces that tool without changing default Raw RAG answering.

## Goals / Non-Goals

**Goals:**

- Add `GraphRetriever` as a backend service that returns structured graph evidence.
- Add a read-side `GraphQueryProvider` protocol for entity, neighbor, and path queries.
- Extend `Neo4jGraphStore` with read methods while preserving optional Neo4j import behavior.
- Support `entity_search(question)`, `neighbor_search(entity_id, depth)`, `path_search(source_entity, target_entity, max_depth)`, and `graph_context_build(paths, entities)`.
- Validate node and relation types against the existing KG allowlists.
- Require every returned relation and graph path edge to contain `source_chunk_id`.
- Resolve returned `source_chunk_id` values through `DocumentRepository.get_chunk()`.
- Return graph entities, relations, paths, source chunk ids, confidence, and evidence chunk metadata for later Agent tools.

**Non-Goals:**

- Do not implement the Agent FSM, QueryRouter, RetrievalPlanner, or tool planner.
- Do not replace or modify default Raw RAG retrieval.
- Do not make `/rag/query` or `/chat/stream` use graph retrieval by default.
- Do not generate final natural-language answers from graph evidence.
- Do not build frontend graph visualization.
- Do not treat graph evidence without raw source chunks as valid evidence.

## Decisions

### Decision 1: Add a separate read-side graph provider protocol

Define a `GraphQueryProvider` with read methods for entity search, neighbor traversal, and path search. `Neo4jGraphStore` can implement both the existing write-side `GraphStoreProvider` and the new read-side protocol.

Rationale: Graph writing and graph retrieval have different contracts. Keeping read and write methods separated makes testing easier and keeps future graph backend replacements clean.

Alternative considered: add read methods directly to `GraphStoreProvider`. This was rejected because ingest only needs writes, while GraphRetriever only needs reads.

### Decision 2: GraphRetriever returns structured evidence only

`GraphRetriever` should return models such as `GraphRetrievalResult` and `GraphContext`, not a final answer string.

Rationale: This keeps the tool deterministic and composable. The later Agent workflow can decide whether graph evidence is enough, whether Raw RAG evidence should be added, and how the final answer should cite sources.

Alternative considered: make GraphRetriever generate summaries. This was rejected because it blurs retrieval and generation and makes citation verification harder.

### Decision 3: Source chunk validation is mandatory

Every returned relation must include `source_chunk_id`, and every path must expose source chunk ids that can be resolved through `DocumentRepository.get_chunk()`. Relations with missing or unresolvable source chunks are filtered or marked invalid and excluded from confidence calculations.

Rationale: The graph is derived evidence, not the source of truth. The system must be able to prove that each graph edge came from raw evidence.

Alternative considered: return graph paths even when evidence chunks are missing. This was rejected because it would let graph structure become unsupported fact.

### Decision 4: Entity search should combine graph lookup and optional vector lookup

`entity_search(question)` should query graph names and aliases through the graph provider, and may additionally use `EntityVectorProvider.search_similar()` when configured.

Rationale: Exact and alias lookup is predictable for named entities, while vector lookup helps when the user describes an entity indirectly. Keeping vector lookup optional avoids adding Milvus entity-vector dependency to every graph retrieval test.

Alternative considered: use only entity vectors. This was rejected because many graph searches are exact entity-name lookups and should work without Milvus entity vectors.

### Decision 5: Bound traversal depth

Neighbor and path search must enforce maximum depths from configuration or service defaults. Suggested defaults are `depth=1` for neighbors and `max_depth=3` for paths, with hard caps such as 3 and 5.

Rationale: Unbounded graph traversal can become slow, noisy, and expensive. Bounded traversal fits the intended Agent tool behavior: find compact dependency, impact, and troubleshooting evidence.

Alternative considered: allow arbitrary depth requested by callers. This was rejected because a later Agent could accidentally create broad graph scans.

### Decision 6: Keep default query behavior unchanged

This change may add runtime construction for GraphRetriever, but it must not call GraphRetriever from `/rag/query` or `/chat/stream` by default.

Rationale: Raw RAG remains the stable production path. GraphRetriever should become a tool for a later Agentic retrieval change.

Alternative considered: immediately enrich `/rag/query` with graph paths. This was rejected because the Agent planning and citation verification layer is not part of this change.

## Risks / Trade-offs

- Neo4j read query shape may drift from write schema -> Keep query-shape tests and use the same property names written by KG foundation.
- Entity search can return ambiguous entities -> Return ranked candidates with confidence instead of choosing one silently.
- Path search can return unsupported graph edges -> Filter missing `source_chunk_id` edges and verify chunks in SQLite.
- Large graphs can produce too much context -> Enforce depth/path count limits and confidence scoring.
- Optional entity vector search may be unavailable -> Make vector search fail-open and keep name/alias graph search usable.
- Evidence chunks can be deleted after graph creation -> Return only paths whose source chunks still resolve, and expose debug info for filtered edges.

## Migration Plan

1. Add graph retrieval result models.
2. Add `GraphQueryProvider` protocol.
3. Extend `Neo4jGraphStore` with read-side entity, neighbor, and path queries.
4. Add `GraphRetriever` service using `GraphQueryProvider`, optional `EntityVectorProvider`, and `DocumentRepository`.
5. Add source chunk validation and confidence calculation.
6. Add tests with fake graph providers and fake evidence repositories.
7. Add Neo4j query-shape tests for entity, neighbor, and path reads.
8. Add runtime wiring only where safe, without default query usage.
9. Update architecture and development docs.

Rollback is simple: do not wire or call `GraphRetriever`. Existing Raw RAG and KG write paths remain valid.

## Open Questions

- Should `entity_search(question)` search `entity_mention` in SQLite as a fallback when Neo4j is unavailable? Recommended: add as an optional fallback if it stays read-only and traceable.
- Should GraphRetriever expose an API endpoint now, or remain internal-only for Agent tooling? Recommended: internal-only for this change unless debugging requires a hidden/dev endpoint.
- Should path search accept entity ids only or names too? Recommended: accept either, resolving names through `entity_search` before path lookup.
