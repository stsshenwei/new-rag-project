## 1. Frontend Event Model

- [x] 1.1 Add normalized frontend types for `AgentStreamEvent`, `AgentTimelineStep`, `AgentRunSummary`, and tool summary metadata.
- [x] 1.2 Add private-field scrubber for `chain_of_thought`, `scratchpad`, `private_reasoning`, `raw_prompt`, and `memory_context`.
- [x] 1.3 Add helper utilities for extracting string, number, boolean, arrays, source chunk ids, evidence counts, and timestamps from unknown SSE payloads.

## 2. Event Normalization

- [x] 2.1 Implement pure normalizer for `agent_trace` payloads.
- [x] 2.2 Implement pure normalizer for `tool_call` payloads.
- [x] 2.3 Implement pure normalizer for `tool_observation` payloads.
- [x] 2.4 Implement pure normalizer for `evidence_summary` payloads.
- [x] 2.5 Implement pure normalizer for `citation_verification` payloads.
- [x] 2.6 Ensure unknown SSE payloads are ignored for timeline purposes without breaking token streaming.
- [x] 2.7 Update `/chat/stream` parser in the chat page to append normalized events while preserving `sources`, `reasoning`, `token`, memory, and feedback behavior.

## 3. Timeline Derivation

- [x] 3.1 Implement derived timeline step builder from normalized agent stream events.
- [x] 3.2 Pair tool-call and tool-result events into one timeline step using event id when available and tool/action/order fallback.
- [x] 3.3 Mark unpaired tool-call steps as running.
- [x] 3.4 Map Agent FSM stage names to user-facing Chinese labels.
- [x] 3.5 Map tool names to user-facing labels for Raw RAG, Keyword Search, GraphRetriever, evidence fusion, and citation verification.
- [x] 3.6 Derive run summary with status, completed step count, total known step count, elapsed time, evidence count, and citation status.
- [x] 3.7 Derive partial or failed status when required tool, evidence, or citation events fail.

## 4. Timeline UI Component

- [x] 4.1 Create a dedicated Agent timeline component for assistant messages with normalized events.
- [x] 4.2 Render a compact run header with running/completed/partial/failed status, step counts, and elapsed time.
- [x] 4.3 Render stage steps with readable title, summary, source chunk count, and status indicator.
- [x] 4.4 Render paired tool steps with input summary while running and result summary after completion.
- [x] 4.5 Render evidence fusion summary with evidence count, citation count, used chunk count, graph path count, sufficiency, confidence, and tool counts.
- [x] 4.6 Render citation verification summary with pass/fail status, verified chunk count, invalid chunk count, and summary text.
- [x] 4.7 Show source chunk chips with a visible cap and overflow count.
- [x] 4.8 Keep legacy reasoning panel available as secondary retrieval detail.

## 5. Timeline Interaction And Styling

- [x] 5.1 Default timeline to expanded while an answer is streaming.
- [x] 5.2 Allow timeline collapse/expand after completion while preserving state for the mounted message.
- [x] 5.3 Add running animation for active steps.
- [x] 5.4 Add completed, failed, skipped, and partial visual states.
- [x] 5.5 Add desktop styles that fit the existing chat column.
- [x] 5.6 Add mobile responsive styles for wrapped titles, summaries, and chunk chips.
- [x] 5.7 Ensure timeline does not hide sources, document preview buttons, feedback controls, or memory notices.

## 6. Optional Backend Metadata

- [x] 6.1 Review whether frontend timing is sufficient for elapsed time and ordering.
- [x] 6.2 If needed, add additive `event_id`, `sequence`, `created_at`, or `elapsed_ms` fields to backend agent stream events without changing existing event names.
- [x] 6.3 If needed, emit additive final run summary metadata while preserving existing `final` payload shape.
- [x] 6.4 Ensure backend stream metadata excludes private reasoning and raw prompts.

## 7. Tests

- [x] 7.1 Add frontend tests for normalizing `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, and `citation_verification`.
- [x] 7.2 Add tests for private-field scrubbing.
- [x] 7.3 Add tests for pairing tool call/result events.
- [x] 7.4 Add tests for running, completed, partial, failed, and skipped run summaries.
- [x] 7.5 Add tests or static checks for timeline component labels and no raw internal-only strings in visible text.
- [x] 7.6 Run TypeScript validation for the frontend.
- [x] 7.7 Run relevant backend tests if optional backend event metadata is changed.

## 8. Documentation And Validation

- [x] 8.1 Update frontend chat UI design documentation with the WeKnora-style timeline behavior.
- [x] 8.2 Update backend RAG pipeline documentation if any optional stream metadata is added.
- [x] 8.3 Document that the timeline shows auditable execution summaries, not hidden chain-of-thought.
- [x] 8.4 Run OpenSpec validation for this change.
- [ ] 8.5 Manually smoke test `/chat/stream` with `CHAT_AGENTIC_WORKFLOW_ENABLED=true` and verify timeline, answer streaming, sources, reasoning, and feedback still work.
