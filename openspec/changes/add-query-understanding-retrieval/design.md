## Context

The backend already performs hybrid retrieval through dense vector search plus keyword/BM25 recall, then fuses results before parent recall and answer generation. The current retrieval input is the user's raw question. This works for literal matches, but it is weak when users use domain shorthand, informal terms, or implicit constraints.

Example:

```text
User query: 8个电口
Likely meaning: 8 x RJ-45 / 8 RJ45 Ethernet copper ports
Document wording: 8个 RJ-45 接口 / RJ45 ports
```

The answer model cannot recover if retrieval never finds the right chunks. The system needs a pre-retrieval query-understanding stage that turns user language into normalized domain terms and multiple retrieval queries.

## Goals / Non-Goals

**Goals:**

- Add a query-understanding boundary before dense and keyword retrieval.
- Normalize domain terminology and aliases deterministically where possible.
- Support configurable terminology entries such as `电口 -> RJ-45`.
- Generate multiple retrieval queries from the original query, normalized query, aliases, and optional LLM rewrite.
- Retrieve against multiple query variants and fuse/deduplicate results.
- Keep existing chat and RAG API contracts unchanged.
- Include query-understanding output in debug information when debug mode is enabled.
- Fall back safely to raw-query retrieval if understanding fails.

**Non-Goals:**

- Do not replace dense vector retrieval, BM25 retrieval, reranking, or parent recall.
- Do not require LLM query rewriting for backend startup.
- Do not build a full ontology or product database in this change.
- Do not require users to manually tag every document.
- Do not change answer-generation prompts except where debug metadata or retrieval context requires it.

## Decisions

### Decision 1: Introduce A QueryUnderstanding Service Boundary

Add a service boundary that accepts a raw user question and returns a structured understanding result:

```text
QueryUnderstandingResult
  original_query
  normalized_query
  intent
  constraints
  expanded_terms
  retrieval_queries
  applied_terms
  source: dictionary | llm | fallback | mixed
```

For `8个电口`, a valid result could be:

```json
{
  "original_query": "8个电口",
  "normalized_query": "8个RJ-45",
  "intent": "technical_document_search",
  "constraints": [],
  "expanded_terms": ["电口", "RJ-45", "RJ45", "以太网电接口", "copper Ethernet port"],
  "retrieval_queries": ["8个电口", "8个RJ-45", "8个RJ45", "8个以太网电接口"],
  "applied_terms": [{"term": "电口", "canonical": "RJ-45"}],
  "source": "dictionary"
}
```

### Decision 2: Use Dictionary-First Terminology Normalization

The first implementation loads a configurable terminology dictionary:

```yaml
terms:
  电口:
    canonical: RJ-45
    aliases:
      - RJ45
      - 以太网电口
      - 以太网电接口
      - copper Ethernet port
  光口:
    canonical: SFP
    aliases:
      - SFP+
      - optical port
      - 光纤接口
```

The dictionary is deterministic and local. It should not require a model call to know core product vocabulary.

### Decision 3: Optional LLM Rewrite Supplements The Dictionary

If enabled, an LLM-based rewrite can add additional retrieval queries after dictionary normalization. The prompt must produce bounded JSON and must not replace dictionary canonical terms.

Default behavior is safe without rewrite:

```text
QUERY_UNDERSTANDING_ENABLED=true
QUERY_REWRITE_ENABLED=false
QUERY_TERMS_PATH=./data/terms.yaml
QUERY_REWRITE_MAX_QUERIES=5
```

### Decision 4: Multi-Query Retrieval Uses Existing Fusion

`RAGService.hybrid_retrieve_hits(question)` first obtains query understanding. It then retrieves for each query variant:

```text
original query
normalized query
alias-expanded retrieval queries
optional LLM rewrites
```

Each retrieval variant can run dense retrieval and keyword retrieval. All hits merge by chunk identity and use the existing RRF/fusion path with trace metadata showing which query variant matched.

### Decision 5: Debug Info Shows Query Understanding

When retrieval debug is enabled, responses include `query_understanding` plus the existing dense, BM25, fused, reranked, and selected parent debug data.

### Decision 6: Fail Open To Raw Query

If dictionary loading fails, LLM rewrite fails, or query-understanding output is invalid, the system continues with the raw question.

## Risks / Trade-offs

- Incorrect terminology can over-expand a query; keep dictionary entries explicit, debug-visible, and easy to edit.
- Too many query variants can increase latency; cap retrieval query count and deduplicate early.
- LLM rewrite may hallucinate terms; keep rewrite default-disabled and validate structured output.
- Dictionary maintenance can drift; document where terms live and add tests for high-value aliases.
- Multi-query retrieval can overweight repeated chunks; use chunk-id dedupe and trace metadata rather than simple concatenation.

## Migration Plan

1. Add query-understanding models and dictionary loader with disabled-safe defaults.
2. Add tests for dictionary normalization, `8个电口 -> RJ-45`, invalid dictionary fallback, rewrite fallback, and query count caps.
3. Wire query understanding into `RAGService.hybrid_retrieve_hits()`.
4. Extend retrieval debug info with query-understanding output.
5. Add optional LLM rewrite behind config with tests using a fake rewrite client.
6. Update documentation and example terminology config.

Rollback strategy:

- Set `QUERY_UNDERSTANDING_ENABLED=false`.
- Keep existing raw-query dense/BM25 retrieval path unchanged.
