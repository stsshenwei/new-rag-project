## Context

The project now has an agentic chat stream path that can emit `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, and `citation_verification` events. The frontend normalizes those events into an agent timeline, and the answer still streams through the existing Markdown renderer.

The remaining product gap is presentation quality: the user wants an experience similar to WeKnora's intelligent-reasoning mode, where the visible process reads like a natural workflow rather than a developer trace. The answer should start with a concise retrieval status, the process timeline should show public execution steps, and how-to answers should reliably produce structured Markdown with copyable commands.

This change is intentionally a polish and answer-formatting change. It should not alter retrieval algorithms, graph traversal, agent planning, citation verification semantics, memory extraction, or authorization.

## Goals / Non-Goals

**Goals:**

- Show a compact per-answer search summary above or near the assistant answer.
- Convert raw agent event names and technical summaries into WeKnora-style user-facing progress copy.
- Make the difference between quick Raw RAG and intelligent reasoning visible: Raw RAG can show summary/citations, while agentic chat shows a timeline of public workflow steps.
- Keep a collapsible audit trail without exposing hidden chain-of-thought.
- Make how-to answers consistently structured as prerequisites, steps, commands, notes, and source-grounded uncertainty.
- Render Markdown code blocks with a language label and copy-code control.
- Preserve current `/chat/stream` compatibility, sources, reasoning, memory, feedback, and document preview behavior.

**Non-Goals:**

- No changes to Raw RAG retrieval, hybrid scoring, reranking, KG extraction, GraphRetriever, or Agent FSM planning.
- No LangChain/free-agent migration.
- No new backend route or SSE event name requirement.
- No citation popover, chunk drawer, or source document redesign.
- No login, tenant, RBAC, or knowledge-base selection UI.
- No hidden chain-of-thought display.

## Decisions

### Derive Search Summary In The Frontend

The frontend will derive search summary state from existing message fields:

- `sources`
- `agentEvents`
- `evidenceSummary`
- `citationVerification`
- `agentCompleted`
- stream loading state

The visible Chinese copy must be valid UTF-8 and should use:

- `检索中...`
- `检索完成 · 引用了 N 篇文档`
- `证据不足`
- `引用校验失败`

Rationale: existing SSE payloads already contain enough evidence and citation state. Deriving in the frontend avoids backend contract churn.

Alternative considered: add a new backend `search_summary` event. Rejected for this change because it would duplicate data and increase stream compatibility risk.

### Keep Detailed Trace But Add Intelligent-Reasoning Timeline Projection

`agent-stream.ts` should keep normalized event data but derive a more product-oriented timeline:

```text
已完成问题理解
检索知识库：[query]
找到 N 个结果
引用了 N 篇文档
思考
完成
```

Tool names and raw FSM stages can remain in metadata or secondary detail, but visible titles should avoid internal class names such as `RawRAGTool`, `FuseEvidence`, or `NeedMoreEvidence`.

Rationale: users care about progress and trust, not implementation structure.

Alternative considered: hide the timeline and only show a top summary. Rejected because the user explicitly wants a visible process flow similar to the screenshots.

### Present Tools As Public Actions

Tool events should be projected into user-facing actions:

- `RawRAGTool` -> `检索知识库`
- `KeywordSearchTool` -> `关键词检索`
- `GraphRetrieverTool` -> `查询图谱证据`
- citation verification -> `校验引用`
- evidence fusion/rerank/context build -> `整理证据`
- answer generation -> `思考`

The primary timeline should avoid implying that private model reasoning is being shown. The `思考` step represents public answer organization and evidence checking only.

### Treat Smart Reasoning As FSM Agentic Chat, Not Free ReAct

This project should keep its current finite-state Agentic Workflow. The WeKnora reference is useful for interaction design, but this change should not require a free-form ReAct loop or LangChain Agent migration.

Rationale: the current enterprise direction prioritizes deterministic tool planning, citation verification, and auditable retrieval behavior.

### Use Prompt Guidance For How-To Structure

`RAGService.stream_answer()` will add answer-style guidance to the user prompt when a question appears to be how-to/procedure oriented. The prompt should require:

- Markdown headings and ordered steps.
- Fenced code blocks for shell commands and config snippets.
- No unsupported external install parameters.
- Explicit `无法确定` wording when evidence is insufficient.
- Source-grounded language such as `根据提供的文档信息`.

Rationale: the existing answer generation path already receives retrieved context; lightweight prompt shaping gives the most value without introducing a new answer generator.

Alternative considered: create separate LLM provider classes for answer styles. Rejected for this change because provider abstraction is not the requested work and would broaden scope.

### Enhance ReactMarkdown Components Instead Of Replacing Markdown Renderer

The chat page will continue using `react-markdown` with `remark-gfm`, but code block rendering will be customized to show a language label and copy button.

Rationale: this preserves existing Markdown behavior and keeps the change local to the frontend.

Alternative considered: switch to MDX or a different Markdown package. Rejected because it adds dependency and migration risk for little benefit.

### Continue To Treat Timeline As Audit Summary

Visible process text must be a public audit summary. Private fields remain scrubbed and must not be surfaced:

- `chain_of_thought`
- `scratchpad`
- `private_reasoning`
- `raw_prompt`
- `memory_context`

Rationale: enterprise knowledge systems need traceability without exposing private model deliberation or prompt internals.

## Risks / Trade-offs

- Product timeline may oversimplify complex tool execution -> keep detailed reasoning panel as secondary audit detail.
- Citation count can be misleading if multiple chunks come from one document -> label as `引用了 N 篇文档` only when deduped by source, otherwise show a neutral citation count.
- How-to prompts may over-format non-how-to questions -> gate format guidance through query-type detection or conservative keyword heuristics.
- Code copy buttons require client-side clipboard support -> provide graceful fallback to regular selectable code.
- Existing visible text includes some encoding corruption from prior changes -> clean affected user-facing strings while implementing this change.
- A WeKnora-like timeline could be mistaken for hidden chain-of-thought -> label and implement it as public execution summary only.

## Migration Plan

1. Add pure frontend helper functions for search summary derivation and product timeline projection.
2. Update `AgentTimeline` to render product copy while keeping detailed metadata available.
3. Add a search summary component to assistant messages.
4. Add custom Markdown code block rendering with copy button and language label.
5. Add how-to answer guidance to backend prompt assembly.
6. Add tests for summary derivation, timeline projection, code block rendering labels, and how-to prompt behavior.
7. Update docs and run frontend/backend validation.

Rollback: remove the search summary component, restore the previous timeline projection, and keep standard `ReactMarkdown` rendering. Backend prompt guidance can be removed without data migration.

## Open Questions

- Should `引用了 N 篇文档` count unique source documents or source chunks? The reference screenshot implies documents, so implementation should prefer unique source paths.
- Should the product timeline be collapsed by default after completion, or should it remain expanded for short traces?
- Should how-to detection rely only on `QueryRouter` route metadata when agentic chat is enabled, with keyword fallback for Raw RAG mode?
