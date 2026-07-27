## Context

The current `/chat/stream` path creates or continues a conversation, optionally recalls long-term memory, performs one hybrid RAG retrieval pass for the user's latest question, emits sources and reasoning, streams an answer, and then persists the assistant response. This works for direct questions but is weak for complex prompts that require comparison, multi-hop lookup, troubleshooting, or procedural planning.

The system already has useful lower-level retrieval components:

- `QueryUnderstandingService` expands and normalizes one query.
- `RAGService.hybrid_retrieve_hits()` performs dense/BM25 retrieval and fusion.
- `RAGService.recall_parent_hits()` expands child hits into context.
- `/chat/stream` already emits a visible `reasoning` summary and now supports conversation/memory context.

Agent decomposition should sit above existing retrieval instead of replacing it.

## Goals / Non-Goals

**Goals:**

- Detect when a user question benefits from decomposition.
- Generate a bounded, structured plan of subquestions with purpose metadata.
- Retrieve evidence for each subquestion using the existing RAG pipeline.
- Aggregate evidence into a final context for answer generation.
- Show a Codex-like visible planning and execution summary to the user.
- Preserve backwards compatibility for simple questions and existing SSE clients.
- Fail open to the current single-pass RAG path when planning or subquestion retrieval fails.

**Non-Goals:**

- Expose hidden chain-of-thought or raw model deliberation.
- Replace the existing query understanding, hybrid retrieval, reranking, memory, or feedback systems.
- Build a general autonomous tool-using agent with arbitrary actions.
- Add parallel execution as the first implementation.
- Guarantee that every complex question can be decomposed perfectly.

## Decisions

### Decision 1: Add Agent Services Above RAGService

Add a `QuestionDecomposer` and `AgenticRetrievalService` above `RAGService`.

`QuestionDecomposer` owns:

- simple vs complex question decision
- structured JSON plan generation
- subquestion limit enforcement
- invalid-plan fallback

`AgenticRetrievalService` owns:

- calling the decomposer
- running retrieval per subquestion
- deduplicating and aggregating evidence
- building visible agent trace payloads
- returning a fallback single-pass result when needed

Rationale: `RAGService` should remain the retrieval/answer layer. Agent orchestration is a distinct planning layer and will otherwise make `RAGService` too broad.

Alternative considered: add decomposition directly inside `RAGService.hybrid_retrieve_hits()`. This was rejected because it would blur one-query retrieval with multi-step planning and make fallback/debug events harder to test.

### Decision 2: Decompose Before Query Understanding

The agent planner receives the original question plus conversation/memory context. Each generated subquestion then goes through the existing query understanding and retrieval pipeline.

Rationale: query understanding improves one query; decomposition decides how many queries should exist. Running query understanding first can help terminology, but it does not solve the structural problem of multi-part questions.

Flow:

```text
question + conversation/memory context
  -> QuestionDecomposer
  -> subquestions
  -> per-subquestion QueryUnderstandingService + hybrid retrieval
  -> evidence aggregation
  -> final answer
```

### Decision 3: Use Structured Plans, Not Free Text

The planner output must be parsed into a typed structure:

```json
{
  "should_decompose": true,
  "question_type": "comparison",
  "reason": "The user asks for differences across multiple dimensions.",
  "subquestions": [
    {
      "id": "sq1",
      "question": "What are the core specifications of product A?",
      "purpose": "Gather evidence for product A."
    }
  ]
}
```

Rationale: structured plans are testable, renderable in the UI, and easy to cap. Free-text plans are brittle and invite leaking hidden reasoning.

### Decision 4: Visible Reasoning Is An Audit Summary

The system will expose an audit summary of explicit planning and execution:

- decomposition decision
- subquestions
- retrieval progress
- source/evidence summaries
- fallback reason when applicable

It will not expose hidden model chain-of-thought.

Rationale: users want Codex-like transparency, but product code should expose controllable process artifacts, not raw internal deliberation.

### Decision 5: Start With Serial Execution

The first implementation runs subquestion retrieval serially.

Rationale: serial execution keeps SSE ordering, logging, tests, and error handling simple. Parallel retrieval can be added later once behavior is stable.

Alternative considered: run all subquestions concurrently. This may reduce latency but complicates cancellation, timeout handling, event ordering, and test determinism.

### Decision 6: Conservative Defaults And Fallback

Decomposition should be behind environment controls:

- `QUESTION_DECOMPOSITION_ENABLED`
- `QUESTION_DECOMPOSITION_MAX_SUBQUESTIONS`
- `QUESTION_DECOMPOSITION_TIMEOUT_SECONDS`

Fallback rules:

- disabled -> current single-pass RAG
- planner error -> current single-pass RAG
- invalid JSON -> current single-pass RAG
- no valid subquestions -> current single-pass RAG
- all subquestions fail -> current single-pass RAG

Rationale: this feature can increase latency and cost; it should be safe to disable and safe when partial failures happen.

### Decision 7: SSE Events Remain Backwards-Compatible

Add optional events:

- `agent_plan`
- `agent_step`
- `subquestion_sources`

Keep existing events:

- `conversation_id`
- `sources`
- `reasoning`
- `token`
- `memory_updated`
- `[DONE]`

Rationale: existing frontend parsers ignore unknown events encoded as JSON fields; preserving old events avoids breaking current chat behavior.

## Risks / Trade-offs

- Higher latency and cost -> Limit max subquestions, keep simple-question fast path, add timeout and env disable switch.
- Poor decomposition quality -> Use structured schema validation and fallback to original question.
- Evidence mixing across subquestions -> Preserve `subquestion_id` and `subquestion` metadata through aggregation and prompt formatting.
- Duplicate sources -> Deduplicate by `doc_id`, `parent_id`, `chunk_id`, and source label while preserving matched subquestions.
- User confusion from "thinking" UI -> Label the panel as "plan/evidence path" and avoid presenting it as hidden thought.
- SSE complexity -> Add tests for event ordering and maintain old `sources` and `token` behavior.

## Migration Plan

1. Add planner and agentic retrieval services with the feature disabled by default.
2. Add backend tests for simple-question fallback, complex-question decomposition, aggregation, and SSE events.
3. Add frontend parsing/rendering for optional agent events.
4. Enable the feature locally through env for smoke testing.
5. If issues appear, set `QUESTION_DECOMPOSITION_ENABLED=false` to return to existing single-pass RAG behavior.

## Open Questions

- Should decomposition be disabled by default until a manual smoke test is complete?
- Should planner generation use the existing OpenAI chat model, a cheaper model, or a deterministic local heuristic first?
- Should final answer generation receive grouped subquestion evidence only, or both grouped evidence and a deduplicated global context?
- Should frontend display per-subquestion sources by default or keep them collapsed under the thinking panel?
