## 1. Prompt Template Catalog

- [x] 1.1 Add backend prompt template directory and an adapted `agent_system_prompt.yaml` with `progressive_rag_agent` and `pure_agent`.
- [x] 1.2 Implement a prompt template loader that validates template ids, modes, defaults, and required content fields.
- [x] 1.3 Implement placeholder rendering for language, web-search status placeholder, bound knowledge-base metadata, available tools, and skill metadata.
- [x] 1.4 Add configuration for prompt template path and selected reasoning template id.
- [x] 1.5 Add tests for valid template loading, missing template handling, invalid id handling, and secret-free rendering.

## 2. Tool Registry Foundation

- [x] 2.1 Create Python runtime tool protocol/classes with name, description, JSON schema parameters, and execute contract.
- [x] 2.2 Implement `ToolRegistry` with first-wins duplicate rejection, stable sorted function definitions, argument validation, safe scalar coercion, output truncation, and cleanup hooks.
- [x] 2.3 Add recoverable tool error observations with retry guidance and structured log fields.
- [x] 2.4 Add environment configuration for enabled tools, max tool output size, tool timeout, and max iterations.
- [x] 2.5 Add unit tests for registry ordering, duplicate rejection, validation failure, output truncation, and error observations.

## 3. Document Runtime Tools

- [x] 3.1 Implement `thinking` as a safe status/reflection tool that never exposes hidden chain-of-thought directly.
- [x] 3.2 Implement `todo_write` for per-run task planning state and trace summaries.
- [x] 3.3 Implement `knowledge_search` by wrapping existing hybrid/vector retrieval and returning bounded candidate evidence with document/chunk identifiers in backend metadata.
- [x] 3.4 Implement `grep_chunks` by wrapping existing keyword/FTS retrieval with bounded match snippets.
- [x] 3.5 Implement `list_knowledge_chunks` to deep-read full chunk content by document, parent, or chunk identifiers through existing repository boundaries.
- [x] 3.6 Implement `get_document_info` to return bounded document metadata, summaries, type, timestamps, chunk counts, and processing status.
- [x] 3.7 Implement `query_knowledge_graph` by wrapping the existing graph retriever when configured and returning a clear disabled observation otherwise.
- [x] 3.8 Add tests for each tool, including cross-knowledge-base scope enforcement and disabled-provider behavior.

## 4. ReAct Runtime Loop

- [x] 4.1 Implement `AgentRuntime` service that builds messages from YAML prompt, conversation context, selected knowledge base scope, temporary attachments metadata, and tool definitions.
- [x] 4.2 Implement the think-act-observe loop using model tool calls, registry execution, observation appending, max iteration handling, empty response retry handling, and repeat-loop detection.
- [x] 4.3 Add mandatory deep-read enforcement after `knowledge_search` or `grep_chunks` returns candidates.
- [x] 4.4 Add final answer generation from verified observations when evidence is sufficient.
- [x] 4.5 Add explicit insufficient-evidence behavior when deep-read evidence or citation verification is insufficient.
- [x] 4.6 Wire `/chat/stream` reasoning mode to use the new runtime only when `AGENT_RUNTIME_ENABLED=true`.
- [x] 4.7 Preserve existing deterministic reasoning workflow as fallback when the new runtime is disabled.
- [x] 4.8 Add tests for successful multi-round retrieval, skipped deep-read correction, max-iteration fallback, and quick-mode isolation.

## 5. Runtime Skills

- [x] 5.1 Add preloaded runtime skill directory structure and migrate read-only reference skills from Weknora where applicable, excluding wiki-specific skill content.
- [x] 5.2 Implement skill metadata discovery with invalid-skill warnings and startup resilience.
- [x] 5.3 Implement `read_skill` with strict path safety, bounded output, unknown-skill errors, and no arbitrary filesystem access.
- [x] 5.4 Add prompt integration so skill names and descriptions are visible only when runtime skills are enabled.
- [x] 5.5 Ensure `execute_skill_script` is not exposed and returns unavailable if requested.
- [x] 5.6 Add tests for disabled skills, valid skill reads, missing skills, traversal rejection, and system-prompt priority over skill instructions.

## 6. Runtime Trace And Observability

- [x] 6.1 Add runtime trace event models for agent execution, rounds, tool calls, observations, evidence sufficiency, citation verification, and final answer.
- [x] 6.2 Stream trace events through existing SSE payload names or backwards-compatible extensions.
- [x] 6.3 Sanitize trace payloads to remove private reasoning, raw prompts, memory context, raw provider payloads, and secrets.
- [x] 6.4 Persist backend spans for agent execution, rounds, and tool calls when span persistence is configured.
- [x] 6.5 Include request trace id in runtime logs and tool logs for correlation with `backend/log/app.log`.
- [x] 6.6 Add tests for trace sanitization, event ordering, span persistence, and log trace-id correlation.

## 7. Frontend Compatibility

- [x] 7.1 Update frontend agent-stream normalization to accept ReAct round, tool call, observation, and skill-read events without breaking current timeline events.
- [x] 7.2 Add user-friendly labels for new runtime tools while avoiding internal parameter names and raw ids.
- [x] 7.3 Ensure clients that ignore trace events still render streamed answer tokens and sources correctly.
- [x] 7.4 Add UI regression checks for quick mode, reasoning mode, and runtime-disabled fallback.

## 8. Documentation And Validation

- [x] 8.1 Update backend RAG/agent design docs with the new runtime architecture, configuration, fallback behavior, and excluded wiki/web/script scopes.
- [x] 8.2 Update `.env.example` with prompt template, runtime enablement, tool limit, max iteration, max output, and skills toggles.
- [x] 8.3 Add backend unit and integration tests for prompt templates, tools, runtime loop, skills, trace, and chat stream routing.
- [x] 8.4 Run targeted backend tests for agent runtime and existing retrieval workflow compatibility.
- [x] 8.5 Run frontend lint/build or targeted checks for chat timeline compatibility.
- [x] 8.6 Manually smoke test `/chat/stream` quick mode, reasoning mode with runtime disabled, and reasoning mode with runtime enabled against a local knowledge base.
