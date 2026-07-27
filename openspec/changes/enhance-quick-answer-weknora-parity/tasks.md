## 1. Baseline And Tests

- [x] 1.1 Add or update backend tests that document the current quick-mode SSE order for `sources`, `reasoning`, `agent_trace`, `token`, and `[DONE]`.
- [x] 1.2 Add backend tests for the required quick trace stages: question understanding, knowledge-base retrieval, evidence reading, answer synthesis, and completion.
- [x] 1.3 Add backend tests proving quick mode does not call the reasoning-mode `AgentRuntime` or open-ended tool loop.
- [x] 1.4 Add answer-guidance tests for compatibility, support, adapter, authentication, port/rate, and technical-parameter questions.
- [x] 1.5 Add insufficient-evidence tests for missing compatibility or parameter details.

## 2. Quick RAG Execution Trace

- [x] 2.1 Add a bounded quick trace builder in `RAGService` that derives public stages from question, scope, retrieval debug metadata, hits, sources, and selected context.
- [x] 2.2 Replace the single Raw RAG `AnalyzeQuestion` quick trace with the richer five-stage quick trace while preserving `AGENT_TRACE_STREAM_ENABLED`.
- [x] 2.3 Include retrieval query count, candidate/hit counts, cited document count, matched chunk ids, knowledge-base scope, and insufficient-evidence status in sanitized metadata.
- [x] 2.4 Ensure quick trace summaries are Chinese user-facing audit summaries and contain no private reasoning, raw prompt, memory context, secrets, or unbounded payloads.
- [x] 2.5 Preserve the existing `/chat/stream` event order and compatibility for clients that only understand old event fields.

## 3. Grounded Markdown Synthesis

- [x] 3.1 Add a conservative classifier for compatibility/support/adapter/parameter question types in the answer-guidance path.
- [x] 3.2 Add prompt guidance that requires direct conclusion, fully supported items, partial support, and technical parameters only when evidence supports those sections.
- [x] 3.3 Require same-source or same-product evidence for product attributes such as model, series, port count, cable support, authentication method, access rate, and parameter value.
- [x] 3.4 Require explicit "根据提供的文档无法确定" style wording when retrieved evidence does not support a requested detail.
- [x] 3.5 Keep default quick-answer behavior concise but Markdown-structured for unrelated factual questions.

## 4. Frontend Timeline Presentation

- [x] 4.1 Update `frontend/app/lib/agent-stream.ts` labels and normalizer handling for the quick trace stages if existing labels are unclear.
- [x] 4.2 Ensure the quick timeline summary avoids misleading "调用 N 次工具" language when no actual tool calls occurred.
- [x] 4.3 Add or update frontend normalizer tests for quick-mode stage rendering, completion state, and collapsed summary text.
- [x] 4.4 Verify the timeline still renders reasoning-mode agent/tool events without regression.

## 5. Documentation And Validation

- [x] 5.1 Update `docs/design-docs/backend-rag-pipeline.md` with the quick-answer trace and grounded synthesis behavior.
- [x] 5.2 Update `docs/design-docs/frontend-chat-ui.md` with quick timeline presentation expectations.
- [x] 5.3 Run the relevant backend unit tests for chat streaming, RAG service answer guidance, and agent trace safety.
- [x] 5.4 Run frontend tests or `npm run build` to verify timeline normalization and chat UI compile.
- [x] 5.5 Perform one manual smoke test with a compatibility question and confirm the UI shows understanding, retrieval, citation, synthesis, completion, and a structured Markdown answer.
