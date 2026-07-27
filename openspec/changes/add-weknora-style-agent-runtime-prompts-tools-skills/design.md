## Context

The project already has a deterministic agentic retrieval workflow for `/rag/query` and `/chat/stream`. It routes a question, plans approved retrieval tools, executes those tools in a fixed order, fuses evidence, verifies citations, and streams safe trace events. This is useful, but it differs from Weknora's intelligent reasoning runtime, where the model receives function definitions and iteratively chooses tools in a ReAct loop.

Weknora's non-wiki agent runtime has four major pieces worth adapting:

- YAML prompt templates such as `progressive_rag_agent`, `pure_agent`, and `data_analyst`
- a tool registry that exposes function definitions, validates arguments, executes tools, truncates outputs, and emits trace/log records
- a ReAct loop that alternates model responses, tool execution, observations, and final synthesis
- preloaded skills that are discovered progressively and loaded through `read_skill`

This change keeps the current quick mode and deterministic retrieval surfaces intact while adding a new runtime path for intelligent reasoning mode.

## Goals / Non-Goals

**Goals:**

- Implement a Weknora-style ReAct runtime for reasoning mode without breaking quick chat mode.
- Load agent system prompts from YAML templates and render safe placeholders for language, bound knowledge bases, available tools, and available skills.
- Expose a stable tool registry with safe default tools for document RAG: thinking, todo planning, semantic search, keyword search, deep chunk read, document metadata, and knowledge graph lookup.
- Enforce mandatory deep reading after search results before final factual answers.
- Add read-only runtime skill discovery and `read_skill` support for preloaded skills.
- Stream and persist safe agent traces that show rounds, tool calls, observations, errors, and final synthesis without hidden chain-of-thought.

**Non-Goals:**

- Wiki tools, wiki prompt templates, and wiki-specific routing are out of scope.
- `execute_skill_script` is out of scope for the first implementation because it requires a secure script sandbox.
- Web search/fetch and structured data analysis tools are out of scope unless a later change enables them explicitly.
- This change does not replace existing upload, chunking, vector storage, Milvus, SQLite FTS, KG, or quick answer behavior.

## Decisions

### Decision: Add a parallel runtime instead of mutating the deterministic workflow in place

Reasoning mode will route to a new runtime service, tentatively `AgentRuntime`, while the existing `AgenticRetrievalWorkflow` remains available as a compatibility fallback. This avoids destabilizing current SSE behavior and gives the Weknora-style loop a clean boundary.

Alternative considered: rewrite `AgenticRetrievalWorkflow` directly into a ReAct loop. That would reduce duplicate code but would risk regressions in existing trace tests and deterministic query behavior.

### Decision: Use YAML prompt templates with adapted content

The project will add backend prompt template files, for example `backend/config/prompt_templates/agent_system_prompt.yaml`, and a loader that selects templates by id. The first required template is an adapted `progressive_rag_agent`; `pure_agent` can support reasoning when no KB is selected; `data_analyst` remains a placeholder until data tools are implemented.

The template text must be adapted to this product and Python tool names. It must preserve Weknora's evidence-first behavior, mandatory deep read, KB priority, per-turn re-retrieval, user-safe communication, and prompt confidentiality.

Alternative considered: keep using `SYSTEM_PROMPT`. That is simpler but cannot express multiple agent modes, runtime placeholders, or Weknora-style tool guidance cleanly.

### Decision: Implement a Python ToolRegistry with JSON Schema validation

Each runtime tool will provide a name, description, JSON schema, and `execute()` method. The registry will:

- reject duplicate tool names with first-wins behavior
- expose stable sorted function definitions for model calls
- coerce common scalar argument mismatches when safe
- validate arguments before execution
- truncate large outputs
- append a retry hint to recoverable tool errors
- emit structured logs and trace spans

Alternative considered: reuse current `RawRAGTool`, `KeywordSearchTool`, and `GraphRetrieverTool` directly. They can remain implementation delegates, but they do not provide model-facing schemas, validation, or Weknora-style output discipline.

### Decision: Start with read-only document tools

Default enabled tools will be limited to safe, read-only operations:

- `thinking`
- `todo_write`
- `knowledge_search`
- `grep_chunks`
- `list_knowledge_chunks`
- `get_document_info`
- `query_knowledge_graph`
- `read_skill`

`knowledge_search` and `grep_chunks` will wrap existing vector/hybrid and keyword retrieval. `list_knowledge_chunks` will deep-read chunk content from SQLite/document repository. `get_document_info` will return bounded document metadata and summaries. `query_knowledge_graph` will wrap the existing graph retriever when configured.

Alternative considered: add all Weknora tools at once. That would increase security and testing surface, especially for web, SQL, and skill script execution.

### Decision: Represent trace as user-safe events plus backend spans

The runtime will stream high-level events compatible with the existing frontend timeline: round start, model step summary, tool call, observation, error, evidence summary, citation verification, and final answer. It will also write backend spans through the existing observability/logging layer when available.

Hidden model reasoning, raw prompts, scratchpads, raw memory context, and secret configuration must not be sent to the frontend or stored in user-visible audit payloads.

Alternative considered: expose model thinking text directly. That would be easier for debugging but unsafe and inconsistent with current trace sanitization rules.

## Risks / Trade-offs

- [Risk] ReAct loops can spend more tokens and latency than deterministic retrieval. -> Mitigation: enforce `AGENT_RUNTIME_MAX_ITERATIONS`, per-tool timeouts, output truncation, and repeat detection.
- [Risk] The model may skip mandatory deep reading. -> Mitigation: encode deep-read rules in the prompt and enforce a runtime guard that blocks final factual answers when search tools returned document ids but no `list_knowledge_chunks` or `get_document_info` evidence was read.
- [Risk] Tool outputs can poison context or leak internal ids. -> Mitigation: bound outputs, sanitize user-visible summaries, and keep raw ids in backend metadata only.
- [Risk] Skill content may introduce conflicting instructions. -> Mitigation: treat skills as lower priority than system prompt and only expose read-only skill loading in this change.
- [Risk] Existing clients may ignore new event types. -> Mitigation: keep current `token`, `sources`, `reasoning`, `agent_trace`, `tool_call`, and `[DONE]` compatibility.

## Migration Plan

1. Add prompt loader, default templates, and tests without changing runtime behavior.
2. Add tool registry and read-only tools behind disabled-by-default configuration.
3. Add the ReAct runtime behind `AGENT_RUNTIME_ENABLED=false`.
4. Wire `/chat/stream` reasoning mode to use the new runtime only when enabled; otherwise keep the existing deterministic workflow.
5. Update the frontend event normalization only for additive event fields.
6. Enable in development and validate with representative knowledge-base questions.

Rollback is configuration-based: disable `AGENT_RUNTIME_ENABLED` to return reasoning mode to the existing workflow.

## Open Questions

- Should `thinking` be visible as a concise status event, or kept entirely internal with only round summaries visible?
- Should `read_skill` be enabled by default, or only after `AGENT_RUNTIME_SKILLS_ENABLED=true`?
- Should `data_analyst` prompt be included now as a template but hidden until data tools are implemented?
