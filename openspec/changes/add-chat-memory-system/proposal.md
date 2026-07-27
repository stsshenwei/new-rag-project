## Why

The current chat flow treats each request as a standalone RAG query: `/chat/stream` receives only the latest message, retrieves document context, and prompts the model without prior conversation or durable user memory. This prevents natural follow-up questions, long working sessions, and ChatGPT-like behavior where stable user preferences and project facts are remembered across chats.

## What Changes

- Add conversation sessions with stable `conversation_id` values so the backend can persist user and assistant messages.
- Include recent conversation turns in the chat prompt to support short-term context memory.
- Add rolling conversation summaries so long chats can preserve earlier decisions without sending the full transcript every time.
- Add a long-term memory system for durable user/project facts, preferences, and instructions that can be recalled across conversations.
- Add memory extraction after assistant responses, with safeguards for sensitivity, confidence, deduplication, and user-controlled deletion.
- Extend the chat SSE contract in a backwards-compatible way with optional `conversation_id` and memory update events.
- Add frontend behavior for new chats, retained conversation IDs, memory notices, and a memory management surface.
- Keep long-term memory separate from the knowledge corpus and feedback documents so ingest/reindex operations do not erase or pollute user memory.

## Capabilities

### New Capabilities

- `chat-conversations`: Conversation sessions, persisted chat messages, short-term context windows, and rolling summaries for long chats.
- `long-term-memory`: Durable user/project memory extraction, storage, recall, update, deletion, and prompt injection.
- `memory-ui-controls`: Frontend controls for creating new chats, displaying memory updates, and managing saved memories.

### Modified Capabilities

- None.

## Impact

- Backend API: extend `ChatRequest` with optional `conversation_id` and memory controls while preserving existing `{ message }` clients.
- Backend streaming: emit optional SSE events for `conversation_id` and memory updates without changing existing `sources`, `reasoning`, `token`, and `[DONE]` events.
- Backend services: introduce repository/service boundaries for conversations and memory; update `RAGService.stream_answer` or its caller to include conversation and memory context.
- Storage: add SQLite tables for conversations, messages, summaries, and long-term memories; optionally add a separate memory vector collection later.
- Frontend: update `frontend/app/chat/page.tsx` and shared types to track the active conversation, handle new SSE events, expose new-chat behavior, and add memory UI.
- Documentation: update architecture and frontend/backend design docs to describe memory boundaries, privacy rules, and prompt assembly.
