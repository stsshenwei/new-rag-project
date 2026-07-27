## Context

The current chat page already supports `/chat/stream`, conversation memory, selected `knowledge_base_ids`, temporary chat, source rendering, reasoning panels, and agent timeline events. The empty state is minimal, the composer reads like a utility toolbar, and agentic chat is controlled by a backend-level `CHAT_AGENTIC_WORKFLOW_ENABLED` switch rather than a user-visible per-message choice.

The new experience should keep the product focused on Bee as an enterprise knowledge assistant: a calm empty-state home screen, suggested questions, a larger composer, explicit answer mode selection, temporary files for the current question, and knowledge base scope selection. The composer must not expose a model selector.

## Goals / Non-Goals

**Goals:**

- Provide a polished empty chat home with a title, suggested questions, and a large composer.
- Let users choose `快速问答` or `智能推理` for each submitted message.
- Route each chat request according to its requested mode while preserving legacy clients.
- Let users upload files that are used only for the current question.
- Keep knowledge base selection visible inside the composer.
- Preserve existing streaming tokens, safe agent trace UI, memory behavior, feedback, and source display.

**Non-Goals:**

- Do not add a visible model picker.
- Do not add temporary chat attachments to knowledge bases, document lists, vector stores, trace span tables, or permanent upload batches.
- Do not expose hidden chain-of-thought.
- Do not redesign the left navigation in this change.
- Do not replace the existing knowledge-base document upload workflow.

## Decisions

### 1. Use a dedicated empty-state chat home

The empty conversation state will render a centered title such as `Hi，我是 Bee，让你的知识触手可及`, a small `你可以这样问我` label, suggested question chips, and the composer. Once the conversation has messages, the page switches to the normal thread layout and hides the welcome content.

Alternative considered: keep the current topbar-first layout and only restyle the input. This would not solve the weak first-screen experience and would still feel like a form rather than an assistant.

### 2. Make chat mode a per-message request field

The frontend will keep a `chatMode` state with two values:

- `quick`: direct retrieval-answer path, shown as `快速问答`.
- `reasoning`: agentic reasoning path, shown as `智能推理`.

Every new user message stores the selected mode in frontend message state and sends it to `/chat/stream`. The backend adds an optional `chat_mode` field to `ChatRequest`.

Compatibility rule: if `chat_mode` is omitted, old clients keep the current behavior based on existing backend configuration. If `quick` is provided, the backend uses the raw chat path. If `reasoning` is provided, the backend uses the agentic chat path and returns a clear error when the agentic workflow is unavailable.

Alternative considered: keep `CHAT_AGENTIC_WORKFLOW_ENABLED` as the only switch. This makes the UI mode selector misleading and prevents users from choosing speed versus depth per question.

### 3. Pre-upload temporary attachments before streaming chat

Because `/chat/stream` is JSON + SSE, binary files should not be embedded directly in the streaming request. The frontend will upload files to a temporary chat attachment endpoint first, receive `attachment_id` values, and then send those ids with the chat request.

Temporary attachments will be parsed into current-request context only. They are not inserted into document metadata, upload batches, vector store collections, knowledge processing spans, or knowledge base document lists. They should be cleaned up by TTL or successful request cleanup.

Alternative considered: reuse knowledge-base upload batches. That would accidentally persist user files as knowledge documents and conflict with the requirement that attachments only apply to the current question.

### 4. Inject temporary attachment context before answer generation

For `quick` mode, parsed attachment text is added to the prompt context alongside retrieved knowledge base chunks. For `reasoning` mode, parsed attachment text is exposed as request-local evidence that the agentic workflow can use without indexing. Source labels should make clear when evidence came from a temporary attachment.

The implementation should enforce size limits and supported file types, reuse existing safe parsers where possible, and fail gracefully when a temporary file cannot be parsed.

### 5. Keep the composer compact and enterprise-focused

The composer toolbar should contain only core controls: answer mode, upload file, knowledge base scope, and send. The old temporary checkbox and generic hint text should be replaced or folded into the new interaction model. The model selector is intentionally absent.

## Risks / Trade-offs

- Per-message routing may diverge from the existing env-level agentic switch -> keep omitted `chat_mode` backward compatible and add explicit tests for all three cases.
- Temporary attachment parsing can slow the first token -> parse before opening the SSE stream or emit an early safe progress event where appropriate.
- Large attachments can overload prompt context -> enforce size, count, and extracted-text limits; show a clear error when exceeded.
- Attachment evidence might be confused with permanent knowledge base content -> label temporary sources distinctly and never write them to document/vector repositories.
- Reasoning mode may be requested when the agentic workflow is disabled -> surface a clear frontend/backend error instead of silently falling back to quick mode.
