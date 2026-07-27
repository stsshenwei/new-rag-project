## Why

The chat entry screen should feel like an enterprise knowledge assistant instead of a plain message form. Users need a clear welcome title, useful suggested questions, a focused composer, per-message control over quick answering versus deeper reasoning, and the ability to attach files for the current question without polluting the knowledge base.

## What Changes

- Redesign the empty chat state around a centered title, suggested question chips, and a large composer.
- Remove the model selector from the composer; model choice remains an internal/backend concern.
- Add a composer mode control with `快速问答` and `智能推理`.
- Make chat mode selectable per message, so each submitted message can independently choose the direct RAG path or the agentic reasoning path.
- Move knowledge base selection into the composer as a compact retrieval-scope control.
- Add upload entry points for temporary per-message attachments that are used only for the current question and are not added to any knowledge base.
- Preserve current streaming chat behavior, knowledge base selection behavior, conversation memory, source display, reasoning/timeline rendering, and feedback flow.
- Keep hidden chain-of-thought private; intelligent reasoning mode may show safe trace summaries only.

## Capabilities

### New Capabilities

- `chat-home-composer-experience`: Empty chat home screen and composer experience with title, suggested questions, mode controls, temporary attachment control, knowledge base selector, and no model selector.
- `per-message-chat-mode-routing`: `/chat/stream` accepts a per-message mode and routes each request to quick RAG or agentic reasoning independently.
- `temporary-chat-attachments`: Chat messages can include temporary files that are parsed for the current request only and are not persisted as knowledge base documents.

### Modified Capabilities

- None.

## Impact

- Frontend chat page and CSS: empty-state layout, suggested question chips, composer toolbar, mode selector, attachment entry, knowledge base selector, and responsive behavior.
- Frontend chat request handling: send `chat_mode`, selected knowledge base ids, and temporary attachment references with each `/chat/stream` request.
- Backend API: `/chat/stream` request schema gains per-message `chat_mode` and temporary attachment inputs while preserving backward compatibility.
- Backend chat orchestration: choose quick RAG or agentic reasoning per request instead of relying only on a global environment switch.
- Backend attachment handling: parse temporary files, inject them into current-request context, and clean them up without creating knowledge base documents, chunks, or vector records.
- Tests: cover empty-state rendering, composer behavior, quick/reasoning routing, compatibility when `chat_mode` is omitted, temporary attachment lifecycle, and no knowledge base pollution.
