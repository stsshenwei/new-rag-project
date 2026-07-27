## 1. Backend Request Contract

- [x] 1.1 Add a validated `chat_mode` field to `ChatRequest` with supported values `quick` and `reasoning`.
- [x] 1.2 Add `attachment_ids` to `ChatRequest` for temporary chat attachments.
- [x] 1.3 Preserve legacy `/chat/stream` behavior when `chat_mode` is omitted.
- [x] 1.4 Persist selected chat mode in user and assistant message metadata.

## 2. Per-Message Routing

- [x] 2.1 Refactor `/chat/stream` mode selection so `quick` forces the raw chat path.
- [x] 2.2 Refactor `/chat/stream` mode selection so `reasoning` forces the agentic chat path.
- [x] 2.3 Return a clear streaming error when `reasoning` is requested but the agentic workflow is unavailable.
- [x] 2.4 Keep existing SSE events, token streaming, source events, memory updates, and `[DONE]` framing compatible.

## 3. Temporary Attachment Backend

- [x] 3.1 Add a temporary chat attachment storage model with id, filename, content type, size, path, status, timestamps, and optional parse error.
- [x] 3.2 Add a multipart upload endpoint for temporary chat attachments.
- [x] 3.3 Enforce supported extension, size, count, and path-safety validation for temporary attachments.
- [x] 3.4 Reuse existing document parsing utilities where possible to extract request-local attachment text.
- [x] 3.5 Resolve `attachment_ids` inside `/chat/stream` and reject unknown, expired, invalid, or unauthorized ids.
- [x] 3.6 Inject temporary attachment context into the quick chat prompt without writing knowledge base documents or vectors.
- [x] 3.7 Expose temporary attachment evidence to the reasoning workflow as request-local context without indexing it.
- [x] 3.8 Label temporary attachment sources distinctly in stream/source metadata.
- [x] 3.9 Mark attachments consumed or cleanup-eligible after the chat request completes or fails.
- [x] 3.10 Add TTL cleanup for expired temporary attachments.

## 4. Frontend State and Request Flow

- [x] 4.1 Add chat mode state to the chat page with default `quick`.
- [x] 4.2 Add pending temporary attachment state with upload progress, success, and error handling.
- [x] 4.3 Add a temporary attachment upload client helper.
- [x] 4.4 Send `chat_mode`, selected `knowledge_base_ids`, and `attachment_ids` with each `/chat/stream` request.
- [x] 4.5 Store selected mode in the local frontend user/assistant message state.
- [x] 4.6 Handle reasoning-unavailable and attachment errors without leaving the composer stuck in loading state.

## 5. Chat Home and Composer UI

- [x] 5.1 Redesign the empty chat state with Bee title, `你可以这样问我`, suggested question chips, and the composer.
- [x] 5.2 Hide the empty-state title and suggested questions once the message thread has content.
- [x] 5.3 Replace the existing composer toolbar with controls for answer mode, temporary file upload, knowledge base scope, and send.
- [x] 5.4 Remove any visible model selector from the composer.
- [x] 5.5 Move or restyle the knowledge base selector as a compact composer control while preserving multi-select behavior.
- [x] 5.6 Add suggested question chip interactions that fill or submit the composer without losing mode or scope state.
- [x] 5.7 Update responsive CSS so the empty state, composer, and toolbar fit desktop and mobile without overlapping or clipped text.
- [x] 5.8 Keep the visual system blue-focused and consistent with the existing Bee enterprise style.

## 6. Trace, Sources, and Safety

- [x] 6.1 Ensure quick mode keeps a concise source/search summary without unnecessary reasoning timeline noise.
- [x] 6.2 Ensure reasoning mode renders safe agent timeline events when the backend streams them.
- [x] 6.3 Ensure no hidden chain-of-thought is rendered in either mode.
- [x] 6.4 Ensure temporary attachment evidence is distinguishable from knowledge base evidence in UI metadata.

## 7. Tests and Validation

- [x] 7.1 Add backend tests for omitted `chat_mode`, `quick`, `reasoning`, and reasoning-unavailable behavior.
- [x] 7.2 Add backend tests for temporary attachment upload validation, request binding, cleanup, and no knowledge base persistence.
- [x] 7.3 Add frontend tests or component-level checks for empty chat home, composer controls, hidden model selector, mode selection, and knowledge base scope.
- [x] 7.4 Add frontend tests or manual verification for temporary attachment upload states and stream error handling.
- [x] 7.5 Run the relevant backend test suite.
- [x] 7.6 Run the relevant frontend lint/test/build validation.
- [x] 7.7 Manually smoke test quick mode, reasoning mode, selected knowledge bases, temporary attachments, and a new empty chat.
