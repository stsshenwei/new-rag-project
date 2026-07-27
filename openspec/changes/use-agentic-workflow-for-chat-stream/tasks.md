## 1. Stream Models And Configuration

- [x] 1.1 Add or extend agent stream event models for `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, `citation_verification`, `sources`, `reasoning`, `token`, and final result metadata.
- [x] 1.2 Add `CHAT_AGENTIC_WORKFLOW_ENABLED` runtime configuration with default false.
- [x] 1.3 Ensure `build_rag_service()` constructs `AgenticRetrievalWorkflow` when either `/rag/query` agent mode or chat agent mode is enabled.
- [x] 1.4 Add tests for default-disabled chat agent mode and independent `/rag/query` vs `/chat/stream` flags.

## 2. Streaming Workflow API

- [x] 2.1 Refactor `AgenticRetrievalWorkflow` internals so non-streaming and streaming paths share route, plan, permission, tool execution, evidence fusion, sufficiency, context, and verification logic.
- [x] 2.2 Add `stream_query_events()` that yields structured events as FSM states execute.
- [x] 2.3 Emit `tool_call` before each planned tool runs and `tool_observation` after each tool completes, skips, or fails.
- [x] 2.4 Emit `evidence_summary` after fusion and sufficiency checking.
- [x] 2.5 Emit `citation_verification` after verification completes.
- [x] 2.6 Add tests proving state order, tool event order, no arbitrary tools, and parity with `run_query()` for route/plan/tool policy.

## 3. Streaming Answer Generation

- [x] 3.1 Update the streaming workflow to call `RAGService.stream_answer()` with agent-built context and yield `token` events as tokens arrive.
- [x] 3.2 Collect streamed tokens into the final assistant answer for conversation persistence and memory extraction.
- [x] 3.3 Stream explicit insufficient-evidence answers when evidence sufficiency fails.
- [x] 3.4 Prevent unsupported factual completion when citation verification fails; emit verification failure and compatible answer tokens.
- [x] 3.5 Add tests for sufficient evidence token streaming, insufficient evidence, and citation failure.

## 4. Chat Route Integration

- [x] 4.1 Split current `/chat/stream` Raw RAG path into a helper that can remain the fallback path.
- [x] 4.2 Add an agentic `/chat/stream` helper that consumes `stream_query_events()` and converts workflow events to SSE JSON payloads.
- [x] 4.3 Keep `conversation_id` as the first SSE payload.
- [x] 4.4 Emit `sources` and `reasoning` before the first `token` in agentic chat mode.
- [x] 4.5 Preserve assistant message persistence, conversation summarization, memory extraction, and `memory_updated` events after the stream completes.
- [x] 4.6 Add route tests for disabled fallback, enabled agentic stream, event ordering, and memory compatibility.

## 5. SSE Compatibility And Safety

- [x] 5.1 Ensure existing SSE payloads remain compatible: `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, `[DONE]`, and `error`.
- [x] 5.2 Ensure simple clients that ignore unknown agent events can still render final answers from `token` payloads.
- [x] 5.3 Ensure agent process events do not include hidden chain-of-thought, private scratchpad text, raw prompts, or memory context dumps.
- [x] 5.4 Ensure tool call payloads include bounded input summaries and limits only.
- [x] 5.5 Add route tests for old-client compatibility and trace safety.

## 6. Documentation

- [x] 6.1 Update `docs/ARCHITECTURE.md` to show `/chat/stream` can use Agentic Retrieval when configured.
- [x] 6.2 Update `docs/design-docs/backend-rag-pipeline.md` with the agentic chat streaming flow and SSE event order.
- [x] 6.3 Update `docs/DEVELOPMENT.md` with `CHAT_AGENTIC_WORKFLOW_ENABLED` and validation commands.
- [x] 6.4 Update README notes for enabling agentic chat streaming.

## 7. Validation

- [x] 7.1 Run workflow unit tests for streaming events, tool order, sufficiency, and citation failure.
- [x] 7.2 Run `/chat/stream` API tests for Raw RAG fallback and agentic mode.
- [x] 7.3 Run memory compatibility tests for agentic chat streaming.
- [x] 7.4 Run full backend regression tests.
