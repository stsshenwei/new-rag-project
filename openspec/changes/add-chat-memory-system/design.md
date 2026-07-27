## Context

The current backend chat endpoint accepts only the latest message, performs RAG retrieval, emits sources/reasoning/tokens over SSE, and calls the LLM with the retrieved document context plus the current question. The frontend keeps chat messages only in React state. A page refresh, a new browser session, or a follow-up request without explicit restatement loses the conversation state.

The application already has a clean backend orchestration point (`RAGService`), SQLite metadata through `DocumentRepository`, Milvus-backed document retrieval, and a single chat page that owns request flow. The memory design should use these boundaries instead of folding every concern into the document corpus.

## Goals / Non-Goals

**Goals:**

- Support natural follow-up questions within a conversation.
- Preserve long-running conversation context with a bounded prompt budget.
- Persist durable user/project memories across conversations in a ChatGPT-like way.
- Keep user memory separate from knowledge documents, uploads, feedback documents, and ingest/reindex lifecycle.
- Preserve backwards compatibility for existing `/chat/stream` clients that send only `{ "message": "..." }`.
- Provide explicit user controls to view, delete, and disable memory behavior.

**Non-Goals:**

- Multi-user authentication or account management.
- Cloud synchronization of memory across devices.
- Replacing the existing RAG document retrieval pipeline.
- Storing secrets, credentials, or highly sensitive personal data as memory.
- Treating every chat transcript as long-term memory.

## Decisions

### Decision 1: Separate Conversation Memory From Long-Term Memory

Conversation state and durable memory will be separate storage concerns.

- Conversation state stores sessions, messages, and rolling summaries.
- Long-term memory stores stable facts, preferences, instructions, and project context.
- Document RAG continues to own uploaded/source documents and feedback knowledge.

Rationale: conversation history is chronological and often ephemeral; long-term memory is curated and should survive new chats. Mixing either into `backend/data/` would make ingest/reindex behavior unsafe and could surface user preferences as document citations.

Alternative considered: write memories as markdown files under `backend/data/feedback/`. This was rejected because feedback files are retrievable corpus content and are affected by document ingest semantics.

### Decision 2: SQLite First, Optional Vector Memory Later

The first implementation will store conversations and long-term memories in SQLite. Memory recall can start with active memories filtered by scope/type and a lightweight relevance pass. A later phase can add a separate Milvus collection for semantic memory retrieval.

Rationale: the existing app already uses SQLite for business metadata, and the initial memory set is expected to be small. This avoids adding a second vector lifecycle before the behavior is proven.

Alternative considered: immediately create a Milvus `rag_memories` collection. This is useful for scale, but it adds embedding, deletion, and synchronization complexity before the core memory UX exists.

### Decision 3: Add Dedicated Services

Add dedicated repository/service boundaries:

- `ConversationRepository`: SQLite persistence for conversations and messages.
- `ConversationService`: context window selection and rolling summary updates.
- `MemoryRepository`: SQLite persistence for active/archived/deleted memories.
- `MemoryService`: extraction, dedupe/merge, recall, deletion, and prompt formatting.

`RAGService` should remain responsible for document retrieval, source extraction, and answer generation. The chat endpoint or a thin chat orchestration service should compose RAG context, conversation context, and memory context.

Rationale: `RAGService` is already broad. Keeping memory as a separate domain makes deletion, privacy rules, and future UI easier to test.

Alternative considered: add all memory methods directly to `RAGService`. This minimizes files but creates a service that owns unrelated persistence and privacy behavior.

### Decision 4: Backwards-Compatible Chat API

Extend `ChatRequest` with optional fields:

- `conversation_id`
- `memory_enabled`
- `temporary`

Existing clients may continue sending only `message`. If `conversation_id` is absent, the backend creates a new conversation and emits it over SSE before tokens.

Rationale: current frontend and tests depend on `/chat/stream`; breaking the contract would create unnecessary migration risk.

### Decision 5: Prompt Assembly Uses Layered Priority

Prompt assembly should include context in this order:

1. system prompt
2. relevant long-term memories
3. conversation summary
4. recent conversation turns
5. retrieved RAG context
6. current user question

The prompt must clearly label memory as user/project memory and RAG context as document evidence. The model should not cite memory as a source document.

Rationale: labels reduce model confusion. Recent conversation and long-term memory help interpret the question, while document context remains the evidence base for factual RAG answers.

### Decision 6: Memory Extraction Is Conservative

After a successful assistant response, a memory extractor evaluates the latest exchange and existing related memories. It may upsert, merge, archive, or do nothing. It must avoid sensitive data and low-confidence guesses.

Memory candidates should include:

- type: `preference`, `profile`, `project_fact`, `instruction`, or `correction`
- content
- normalized key for deduplication
- confidence
- source conversation/message IDs

Rationale: ChatGPT-like memory is useful only if it is curated. Saving every statement would produce noisy, stale, and privacy-hostile behavior.

Alternative considered: user-only explicit "remember this" commands. This is safer but loses the expected ChatGPT-like convenience. The design still supports explicit remember/forget commands as high-confidence signals.

### Decision 7: User Control Is Required

Users must be able to:

- start a new conversation without deleting long-term memory
- disable memory for a request or temporary chat
- see when a memory was saved or updated
- list saved memories
- delete a memory

Rationale: memory changes assistant behavior across conversations, so the user needs visible control.

## Risks / Trade-offs

- False memory extraction -> Use conservative prompts, confidence thresholds, normalized-key dedupe, and visible deletion controls.
- Sensitive data persistence -> Block obvious secrets/credentials and default to not saving ambiguous sensitive content.
- Prompt bloat -> Limit active memory count, summarize old conversation messages, and keep a bounded recent-turn window.
- Conflicting memories -> Store normalized keys and update existing active memories instead of creating duplicates; prefer recent explicit user instructions.
- UX surprise -> Emit memory update events and show a small notice when something is remembered.
- Test complexity -> Add repository unit tests, API streaming tests, and prompt assembly tests with fake LLM clients.

## Migration Plan

1. Add SQLite tables with `create table if not exists` migrations so existing metadata databases continue to open.
2. Deploy backend support with optional `conversation_id` and memory fields defaulted off or conservative.
3. Update frontend to track conversation IDs and display memory events.
4. Enable short-term conversation context first.
5. Enable summary and long-term memory extraction behind environment flags.
6. Roll back by disabling memory flags; existing conversations/memories remain inert in SQLite and do not affect RAG ingest.

## Open Questions

- Should long-term memory be enabled by default in local development, or guarded by `MEMORY_ENABLED=true`?
- Should project-level memories be scoped to the repository path, a configured workspace ID, or a single local default project?
- Should memory extraction stream an event immediately after `[DONE]`, before `[DONE]`, or be purely visible on the next request?
- Should memory management live in the chat topbar initially, or in a separate settings route?
