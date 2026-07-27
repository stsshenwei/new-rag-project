## Why

> Superseded: this change is not being implemented as a standalone layer. Its visible reasoning trace ideas are folded into `add-agentic-retrieval-workflow`; decomposition can return later as a narrower planner strategy.

The current chat flow answers every user request as a single RAG retrieval pass, even when the question is multi-part, comparative, procedural, or diagnostic. Adding an agentic planning layer allows the system to decompose complex questions, retrieve evidence for each subquestion, and show a Codex-like visible reasoning summary without exposing hidden chain-of-thought.

## What Changes

- Add an agent planner that decides whether a user question should be decomposed.
- Add structured question decomposition into bounded subquestions with purpose metadata.
- Add agentic retrieval orchestration that runs existing RAG retrieval per subquestion and aggregates evidence.
- Add a visible reasoning trace that shows the plan, subquestions, retrieval progress, and evidence path as an audit summary.
- Extend `/chat/stream` with backwards-compatible optional SSE events for agent plan and agent steps.
- Preserve existing simple-question behavior by falling back to the current single-pass retrieval path when decomposition is unnecessary or fails.
- Keep hidden model chain-of-thought private; expose only explicit plan and execution summaries.
- Add frontend rendering for the agent plan and per-subquestion evidence summary.

## Capabilities

### New Capabilities

- `agent-question-decomposition`: Agent planner, structured subquestion generation, per-subquestion retrieval, evidence aggregation, fallback behavior, and final answer composition.
- `agent-reasoning-trace`: User-visible planning and execution summary events for Codex-like thinking UX without exposing hidden chain-of-thought.

### Modified Capabilities

- None.

## Impact

- Backend API: `/chat/stream` may emit optional `agent_plan`, `agent_step`, and `subquestion_sources` SSE events while preserving existing `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` events.
- Backend services: add `QuestionDecomposer` and `AgenticRetrievalService` or equivalent boundaries above `RAGService`.
- Retrieval: complex questions may trigger multiple retrieval calls, increasing latency and LLM/token cost.
- Prompting: final answer prompt will include the original question, visible plan summary, grouped subquestion evidence, existing memory/conversation context, and document context.
- Frontend: chat UI will render an expandable thinking/process panel for the agent plan and evidence path.
- Configuration: add environment controls for enabling decomposition, max subquestions, timeouts, and fallback behavior.
- Tests: add unit tests for decomposition decisions, fallback behavior, evidence aggregation, SSE ordering, and frontend parsing/rendering.
