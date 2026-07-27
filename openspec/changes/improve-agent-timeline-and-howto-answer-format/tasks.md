## 1. Frontend Summary Model

- [x] 1.1 Add a pure helper for deriving assistant search summary state from sources, agent events, evidence summary, citation verification, completion state, and streaming state.
- [x] 1.2 Deduplicate cited document counts by source path instead of raw chunk count when building `引用了 N 篇文档`.
- [x] 1.3 Represent summary statuses for searching, completed, insufficient evidence, citation failure, and empty/no-source states.
- [x] 1.4 Add tests for summary derivation in non-agentic Raw RAG mode.
- [x] 1.5 Add tests for summary derivation in agentic mode with evidence and citation events.

## 2. Search Summary UI

- [x] 2.1 Create a compact search summary component for assistant messages.
- [x] 2.2 Render `检索中...` while retrieval or answer streaming is active and citations are not yet known.
- [x] 2.3 Render `检索完成 · 引用了 N 篇文档` when citable sources are available.
- [x] 2.4 Render insufficient-evidence and citation-failed states clearly.
- [x] 2.5 Place the summary so it does not hide answer text, source buttons, reasoning, feedback, memory notices, or document preview behavior.
- [x] 2.6 Add responsive CSS for the summary row and disclosure affordance.

## 3. Product Timeline Copy

- [x] 3.1 Add a product timeline projection helper that maps normalized agent events into simple visible steps.
- [x] 3.2 Map analysis/routing events to `已完成问题理解`.
- [x] 3.3 Map retrieval tool events to `检索知识库：[query]` and `找到 N 个结果`.
- [x] 3.4 Map source/citation events to `引用了 N 篇文档`.
- [x] 3.5 Map context building and generation events to public answer-organization copy such as `思考` or `整理答案`.
- [x] 3.6 Map final completion to `完成`.
- [x] 3.7 Keep raw tool names and FSM stages out of primary visible titles while preserving audit metadata.
- [x] 3.8 Ensure all visible timeline Chinese strings are valid UTF-8 and not mojibake.
- [x] 3.9 Add tests proving private fields are scrubbed from titles, summaries, and details.
- [x] 3.10 Map `RawRAGTool`, `KeywordSearchTool`, and `GraphRetrieverTool` to public action labels instead of class names.
- [x] 3.11 Ensure the primary timeline appears only when agentic chat events exist; legacy Raw RAG may show the compact summary without pretending to be intelligent reasoning.

## 4. Timeline Component Update

- [x] 4.1 Update `AgentTimeline` to render WeKnora-style product timeline steps by default.
- [x] 4.2 Keep detailed reasoning/audit panel as secondary detail below the product timeline.
- [x] 4.3 Keep running, completed, partial, failed, and skipped visual states.
- [x] 4.4 Preserve collapse/expand behavior during and after streaming.
- [x] 4.5 Ensure timeline still renders useful output when only legacy raw RAG trace data is available.
- [x] 4.6 Use a vertical step layout with clear icons/status marks and compact spacing similar to the reference screenshots.
- [x] 4.7 Keep `思考` as public evidence organization text, not hidden chain-of-thought.

## 5. How-To Prompt Guidance

- [x] 5.1 Add conservative how-to/procedure detection for answer-format guidance.
- [x] 5.2 Add prompt instructions for how-to answers: prerequisites, ordered steps, commands, cautions, and explicit uncertainty.
- [x] 5.3 Require fenced code blocks for commands and config snippets when such text is present in retrieved context.
- [x] 5.4 Require the model not to invent unsupported commands, URLs, versions, flags, or prerequisites.
- [x] 5.5 Preserve existing system prompt, memory context, conversation context, and retrieved context order.
- [x] 5.6 Add backend tests or focused unit tests for how-to prompt assembly behavior.
- [x] 5.7 Prefer final answer sections such as `前提条件`, `在线安装步骤`, `离线安装步骤`, `验证`, and `注意事项` when supported by evidence.
- [x] 5.8 Ensure how-to answers still cite retrieved documents and do not use unsupported web/prior knowledge.

## 6. Markdown Code Block Rendering

- [x] 6.1 Add a custom Markdown code renderer for assistant answers.
- [x] 6.2 Show a language label for fenced code blocks when the language is known.
- [x] 6.3 Add a copy-code button for block code.
- [x] 6.4 Gracefully fall back when clipboard access fails or is unavailable.
- [x] 6.5 Preserve inline code rendering without block controls.
- [x] 6.6 Add CSS for code block header, copy button, scrolling, and mobile width.
- [x] 6.7 Add tests or static checks for code block label and copy-button rendering.

## 7. Compatibility And Safety

- [x] 7.1 Verify `/chat/stream` parsing remains compatible with `sources`, `reasoning`, `token`, `conversation_id`, `memory_updated`, and `[DONE]`.
- [x] 7.2 Verify no new SSE event names are required.
- [x] 7.3 Verify hidden fields `chain_of_thought`, `scratchpad`, `private_reasoning`, `raw_prompt`, and `memory_context` are not displayed.
- [x] 7.4 Verify sources remain clickable and feedback controls still submit corrections.
- [x] 7.5 Verify memory panel and temporary-chat controls remain unaffected.
- [x] 7.6 Verify `CHAT_AGENTIC_WORKFLOW_ENABLED=false` keeps the legacy quick-answer experience.
- [x] 7.7 Verify `CHAT_AGENTIC_WORKFLOW_ENABLED=true` shows the intelligent-reasoning timeline when agent events are present.

## 8. Documentation And Validation

- [x] 8.1 Update frontend chat UI design documentation with the search summary, product timeline, and code block behavior.
- [x] 8.2 Update backend RAG pipeline documentation with how-to prompt guidance.
- [x] 8.3 Run frontend TypeScript validation.
- [x] 8.4 Run frontend unit/static tests for agent stream, summary, timeline, and Markdown rendering helpers.
- [x] 8.5 Run relevant backend tests for prompt assembly.
- [x] 8.6 Run `openspec validate improve-agent-timeline-and-howto-answer-format --strict`.
- [ ] 8.7 Smoke test a how-to question such as `k3s 搭建步骤` with `CHAT_AGENTIC_WORKFLOW_ENABLED=true` when backend services are available.
