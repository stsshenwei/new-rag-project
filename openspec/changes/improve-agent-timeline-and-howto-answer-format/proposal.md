## Why

The current chat experience can stream agent events and render a timeline, but it still feels like a technical trace rather than the polished intelligent-reasoning flow shown by WeKnora. Users need to see the assistant's public execution process: question understanding, knowledge-base search, cited-document count, evidence organization, answer generation, and completion.

This change upgrades the presentation layer and answer-format guidance so the system feels like a real enterprise knowledge assistant, not just a raw RAG debug panel. It does not change the underlying retrieval algorithms or turn the finite-state workflow into a free-form Agent.

## What Changes

- Add a compact retrieval summary above assistant answers, such as `检索中...`, `检索完成 · 引用了 N 篇文档`, `证据不足`, or `引用校验失败`.
- Productize the agent timeline copy so raw stage/tool events become WeKnora-style user-facing steps: `已完成问题理解`, `检索知识库：[query]`, `找到 N 个结果`, `引用了 N 篇文档`, `思考`, and `完成`.
- Distinguish quick Raw RAG presentation from intelligent-reasoning presentation: Raw RAG may show the compact summary and citations; agentic chat SHALL show the step timeline when `CHAT_AGENTIC_WORKFLOW_ENABLED=true` and agent events are emitted.
- Convert tool calls into readable public actions. For example, Raw RAG/keyword/graph retrieval tool events should display as knowledge-base search, keyword search, or graph evidence lookup, while internal class names remain secondary audit metadata.
- Keep the existing detailed reasoning panel available as secondary audit detail.
- Improve how-to answer generation instructions so how-to questions produce sectioned Markdown with prerequisites, steps, command blocks, cautions, and explicit insufficient-evidence behavior.
- Enhance Markdown code block rendering with language labels and a copy-code button.
- Preserve existing `/chat/stream` event names, token streaming, sources, memory, feedback, document preview, Raw RAG, GraphRetriever, and Agent FSM behavior.
- Continue to show only public auditable execution summaries; do not expose hidden chain-of-thought, scratchpads, raw prompts, or memory context.

## Capabilities

### New Capabilities

- `agent-search-summary-ui`: Displays a compact per-answer retrieval/citation status derived from streamed sources, agent events, evidence summary, and citation verification.
- `agent-timeline-product-copy`: Maps normalized agent stream events into a simpler user-facing intelligent-reasoning timeline without exposing internal stage names or hidden reasoning.
- `howto-answer-rendering`: Produces and renders how-to answers as structured Markdown with reliable command-code presentation and copy controls.

### Modified Capabilities

- None.

## Impact

- Frontend chat message rendering in `frontend/app/chat/page.tsx`.
- Agent stream normalization and derived timeline labels in `frontend/app/lib/agent-stream.ts`.
- Timeline component behavior in `frontend/app/components/AgentTimeline.tsx`.
- Markdown rendering and CSS in `frontend/app/chat/page.tsx` and `frontend/app/globals.css`.
- Backend answer prompt assembly in `backend/app/services/rag_service.py`.
- Tests for frontend event derivation, search summary rendering helpers, code block rendering, and how-to prompt behavior.
- Documentation updates for frontend chat UI and backend prompting strategy.

## Acceptance Focus

- A normal Raw RAG answer can still stream exactly as before, with a compact search/citation summary added.
- An agentic chat answer with `CHAT_AGENTIC_WORKFLOW_ENABLED=true` shows a WeKnora-style process timeline before or alongside the final answer.
- The primary timeline does not expose raw FSM state names, tool class names, hidden chain-of-thought, raw prompts, or private memory context.
- A how-to question such as `k3s 搭建步骤` produces a professional Markdown answer with sections and fenced command blocks when those commands are supported by retrieved evidence.
- If the retrieved evidence is insufficient, both the summary and final answer make that clear instead of inventing missing facts.
