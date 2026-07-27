## Why

The current intelligent reasoning mode exposes a useful retrieval trace, but it is still a deterministic backend workflow rather than a Weknora-style ReAct agent that can select tools, deep-read evidence, and adapt across multiple rounds. Adding a runtime agent layer makes the chat experience more faithful to Weknora: prompt-driven, tool-callable, traceable, and extensible through skills.

## What Changes

- Add a Weknora-style agent runtime that supports iterative think-act-observe execution for intelligent reasoning mode.
- Add prompt template loading from YAML so agent behavior is governed by configurable templates instead of only environment variables and hardcoded prompt strings.
- Add a typed tool registry with function definitions, parameter validation, output truncation, error guidance, and stable tool ordering.
- Add document-oriented runtime tools equivalent to Weknora's non-wiki retrieval tools, including semantic search, keyword search, deep chunk reading, document info, knowledge graph lookup, thinking, and todo planning.
- Add runtime skill discovery and read-only skill loading so the agent can consult preloaded skills when user intent matches a skill.
- Keep wiki tools and wiki prompt templates out of scope for this change.
- Defer executable skill scripts, web search/fetch, and structured data analysis tools unless they are explicitly enabled in a later change.

## Capabilities

### New Capabilities
- `agent-runtime-tool-calling`: Defines the ReAct agent runtime, tool registry, tool-call loop, guardrails, and fallback behavior for intelligent reasoning.
- `agent-prompt-templates`: Defines YAML-backed prompt template loading, selection, placeholder rendering, and Weknora-style progressive RAG prompt behavior.
- `runtime-agent-skills`: Defines preloaded runtime skill discovery and read-only skill loading through agent tools.
- `agent-runtime-trace`: Defines user-safe trace events and backend span records for agent rounds, tool calls, observations, and final synthesis.

### Modified Capabilities
- None.

## Impact

- Backend services: agentic chat workflow, chat streaming route, RAG retrieval surfaces, knowledge base document access, and tracing/logging.
- Frontend chat UI: intelligent reasoning timeline may receive richer agent round/tool events and skill/tool labels.
- Configuration: new prompt template files and environment settings for enabling runtime tools, prompt template selection, max iterations, max tool output, and skills.
- Tests: unit tests for prompt loading, tool registry validation, tool execution, ReAct loop outcomes, trace sanitization, and chat stream compatibility.
