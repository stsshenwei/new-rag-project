## 1. Backend Data Model

- [x] 1.1 Add `ConversationRepository` with SQLite tables for conversations and conversation messages.
- [x] 1.2 Add `MemoryRepository` with SQLite tables for long-term memories, status, type, normalized key, source IDs, and timestamps.
- [x] 1.3 Add repository tests covering conversation creation, message append, summary update, memory upsert, memory merge, listing, and deletion.

## 2. Conversation Context

- [x] 2.1 Add `ConversationService` to create/continue conversations and select a bounded recent-message window.
- [x] 2.2 Add rolling summary generation for conversations that exceed the configured threshold.
- [x] 2.3 Add tests proving follow-up requests include recent context and long conversations use summary plus recent messages.

## 3. Long-Term Memory

- [x] 3.1 Add `MemoryService` for memory recall, prompt formatting, extraction, deduplication, update, and deletion.
- [x] 3.2 Implement conservative memory extraction with confidence thresholds and sensitive-content filtering.
- [x] 3.3 Implement explicit remember/forget handling for high-confidence user instructions.
- [x] 3.4 Add tests for stable preference saving, one-off task rejection, sensitive data rejection, duplicate merge, superseded preference handling, and disabled-memory behavior.

## 4. Chat API Integration

- [x] 4.1 Extend `ChatRequest` with optional `conversation_id`, `memory_enabled`, and `temporary` fields while preserving existing `{ message }` requests.
- [x] 4.2 Wire conversation and memory services into app startup/service construction.
- [x] 4.3 Update `/chat/stream` to create or continue conversations, persist user/assistant messages, and emit `conversation_id`.
- [x] 4.4 Update prompt assembly to include labeled long-term memories, conversation summary, recent turns, RAG context, and current question.
- [x] 4.5 Emit optional memory update SSE events without changing existing `sources`, `reasoning`, `token`, and `[DONE]` event behavior.
- [x] 4.6 Add API tests for legacy compatibility, conversation continuation, memory-off requests, and SSE event ordering.

## 5. Memory Management API

- [x] 5.1 Add an endpoint to list active long-term memories.
- [x] 5.2 Add an endpoint to delete or archive a memory by ID.
- [x] 5.3 Add route tests for listing, deletion, unknown IDs, and exclusion of deleted memories from recall.

## 6. Frontend Integration

- [x] 6.1 Extend frontend chat types to include conversation ID, memory update events, memory records, and memory request flags.
- [x] 6.2 Update chat request flow to store streamed `conversation_id` and send it with subsequent messages.
- [x] 6.3 Update new-chat behavior to clear local transcript and active conversation ID without affecting long-term memory.
- [x] 6.4 Add a temporary or memory-off control that sends the correct request flag.
- [x] 6.5 Render non-blocking memory update notices when the stream reports saved or updated memories.
- [x] 6.6 Add a memory management surface for listing and deleting saved memories.

## 7. Documentation And Validation

- [x] 7.1 Update `docs/ARCHITECTURE.md` with the conversation/memory storage boundaries and request flow.
- [x] 7.2 Update `docs/design-docs/backend-rag-pipeline.md` with prompt assembly and memory separation from document ingest.
- [x] 7.3 Update `docs/design-docs/frontend-chat-ui.md` with conversation ID tracking, memory notices, and memory controls.
- [x] 7.4 Run backend tests for repositories, services, and API routes.
- [x] 7.5 Run frontend lint/build validation for the updated chat UI.
- [ ] 7.6 Perform an end-to-end smoke test: ask a follow-up question, start a new chat, verify long-term memory recall, delete a memory, and verify it is no longer used.
