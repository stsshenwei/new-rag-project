## Why

Direct vector retrieval can miss domain-specific intent when users ask with informal or abbreviated language. For example, a user may ask for `8个电口`, while the documents use `8个 RJ-45` or `RJ45 ports`; without query understanding, retrieval may fail before the answer stage has useful context.

## What Changes

- Add a query-understanding stage before dense/BM25 retrieval.
- Normalize domain terms and aliases such as `电口`, `RJ-45`, `RJ45`, and `以太网电接口`.
- Extract structured query intent, constraints, expanded terms, and multiple retrieval queries.
- Add a configurable domain terminology dictionary that can provide deterministic alias expansion.
- Add optional LLM-based query rewriting for cases not covered by the terminology dictionary.
- Run retrieval against the original query plus normalized/expanded retrieval queries and fuse results before parent recall.
- Include query-understanding output in retrieval debug information when debug mode is enabled.
- Preserve existing `/chat/stream` and `/rag/query` API contracts while improving retrieval inputs internally.

## Capabilities

### New Capabilities

- `query-understanding-retrieval`: Defines pre-retrieval query understanding, terminology normalization, query expansion, multi-query retrieval, fusion behavior, debug visibility, and safe fallback behavior.

### Modified Capabilities

- None.

## Impact

- Backend retrieval orchestration in `backend/app/services/rag_service.py`.
- New query-understanding service boundary under `backend/app/services/`.
- Terminology dictionary under `backend/data/terms.yaml`.
- Hybrid retrieval inputs and debug metadata.
- Tests for term normalization, query expansion, multi-query retrieval, fallback behavior, and `8个电口 -> RJ-45` cases.
- Documentation updates for query-understanding configuration and retrieval behavior.
