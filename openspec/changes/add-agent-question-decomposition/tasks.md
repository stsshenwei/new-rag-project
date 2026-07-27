## 1. Agent Planning Models

- [ ] 1.1 Add typed models for decomposition plans, subquestions, agent steps, subquestion evidence, and fallback metadata.
- [ ] 1.2 Add unit tests for valid plans, invalid plans, max-subquestion enforcement, and fallback metadata shape.

## 2. Question Decomposer

- [ ] 2.1 Add `QuestionDecomposer` service with configuration for enabled state, max subquestions, and timeout.
- [ ] 2.2 Implement simple-question bypass and complex-question detection for comparative, multi-condition, procedural, and diagnostic prompts.
- [ ] 2.3 Implement structured planner output parsing with validation and fail-open fallback.
- [ ] 2.4 Add tests for simple bypass, complex decomposition, malformed planner output, planner exceptions, and disabled configuration.

## 3. Agentic Retrieval Orchestration

- [ ] 3.1 Add `AgenticRetrievalService` above `RAGService` to call the decomposer and run retrieval per subquestion.
- [ ] 3.2 Preserve existing single-pass retrieval behavior when decomposition is disabled, unnecessary, or invalid.
- [ ] 3.3 Execute subquestion retrieval serially using existing query understanding, hybrid retrieval, and parent recall.
- [ ] 3.4 Deduplicate evidence by document/source/chunk/parent identity while preserving matched subquestion IDs.
- [ ] 3.5 Add tests for per-subquestion retrieval, isolated subquestion failures, duplicate evidence merging, and no-evidence fallback.

## 4. Prompt And Answer Composition

- [ ] 4.1 Extend answer prompt composition to include original question, visible plan summary, and grouped subquestion evidence.
- [ ] 4.2 Preserve existing memory context, conversation context, document context, and source extraction behavior.
- [ ] 4.3 Add tests proving final answer prompts include grouped evidence without exposing hidden chain-of-thought fields.

## 5. Streaming API Integration

- [ ] 5.1 Wire agentic retrieval into `/chat/stream` behind environment configuration.
- [ ] 5.2 Emit optional `agent_plan` SSE payload before answer tokens when decomposition is used.
- [ ] 5.3 Emit optional `agent_step` SSE payloads for subquestion start, success, and failure statuses.
- [ ] 5.4 Emit optional `subquestion_sources` SSE payloads with grouped source summaries.
- [ ] 5.5 Preserve existing `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` event behavior.
- [ ] 5.6 Add route tests for event ordering, simple-question stream shape, fallback stream shape, and clients ignoring agent events.

## 6. Frontend Agent Reasoning UI

- [ ] 6.1 Extend frontend chat types for `agent_plan`, `agent_step`, and `subquestion_sources` events.
- [ ] 6.2 Update SSE parser to store agent plan and subquestion evidence on the active assistant message.
- [ ] 6.3 Render an expandable thinking/process panel showing decomposition decision, subquestions, step statuses, and evidence path.
- [ ] 6.4 Ensure simple questions do not show an empty agent panel.
- [ ] 6.5 Add frontend build/type validation for the updated event types and UI.

## 7. Configuration And Documentation

- [ ] 7.1 Add environment variables for enabling decomposition, max subquestions, and planner timeout.
- [ ] 7.2 Update `docs/ARCHITECTURE.md` with the agent planning layer and SSE event flow.
- [ ] 7.3 Update `docs/design-docs/backend-rag-pipeline.md` with decomposition, evidence aggregation, and fallback behavior.
- [ ] 7.4 Update `docs/design-docs/frontend-chat-ui.md` with the agent reasoning panel and optional stream events.

## 8. Validation

- [ ] 8.1 Run backend unit and API tests covering decomposer, agentic retrieval, prompt composition, and streaming.
- [ ] 8.2 Run frontend type/build validation.
- [ ] 8.3 Perform a manual smoke test with one simple question and one complex question to verify bypass, decomposition, visible trace, sources, final answer, and fallback controls.
