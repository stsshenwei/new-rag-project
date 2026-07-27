## Why

Bee's quick-answer mode currently retrieves evidence and streams an answer, but the visible execution and final formatting do not match the Weknora quick Q&A behavior the user is comparing against. The gap is most visible on product compatibility questions: Bee shows only a minimal Raw RAG trace and often answers as a plain list, while Weknora shows public RAG stages and synthesizes source-grounded Markdown sections such as full compatibility, partial compatibility, and technical parameters.

## What Changes

- Add a Weknora-inspired quick-answer execution trace for the existing `quick` chat mode: question understanding, knowledge-base retrieval, evidence reading/citation preparation, public synthesis, and completion.
- Keep quick mode as bounded RAG, not ReAct reasoning mode; it must not require `AGENT_RUNTIME_ENABLED=true` or open-ended tool loops.
- Emit additive SSE events compatible with the existing agent timeline UI so quick mode can show "理解问题 / 检索知识库 / 引用了 N 篇文档 / 思考 / 完成".
- Strengthen quick-answer synthesis for compatibility, adapter, support, and technical-parameter questions with source-grounded Markdown sections and tables.
- Add tests and golden cases for quick-mode trace order, evidence counts, Markdown answer guidance, and no-knowledge/insufficient-evidence behavior.
- No breaking API changes. Existing `sources`, `reasoning`, `agent_trace`, and `token` events remain valid.

## Capabilities

### New Capabilities

- `quick-answer-execution-trace`: Defines the public, auditable RAG-stage trace that quick chat streams must emit.
- `quick-answer-grounded-synthesis`: Defines source-grounded Markdown synthesis behavior for quick answers, especially compatibility and technical-parameter questions.

### Modified Capabilities

- None.

## Impact

- Backend: `backend/app/main.py`, `backend/app/services/rag_service.py`, prompt template/catalog usage, retrieval debug summaries, and related tests.
- Frontend: `frontend/app/lib/agent-stream.ts`, `frontend/app/components/AgentTimeline.tsx`, `frontend/app/chat/page.tsx`, and CSS only if existing labels/layout need small quick-mode adjustments.
- Documentation: `docs/design-docs/backend-rag-pipeline.md` and `docs/design-docs/frontend-chat-ui.md` should be updated after implementation.
- Dependencies: no new required runtime dependency; the work should reuse the existing RAG retrieval, prompt catalog, SSE stream, and timeline normalizer.
