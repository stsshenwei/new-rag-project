## Why

Intelligent reasoning mode already has a Weknora-style ReAct runtime and `grep_chunks` tool, but the current prompt and tool contract do not strongly guarantee that the model will use its own parametric knowledge to generate synonym-rich grep arguments before semantic retrieval. This change makes reasoning mode default to LLM-driven grep-first retrieval so factual knowledge-base questions start with exact entity anchoring, deep reading, and evidence-verified synthesis.

## What Changes

- Enable grep-first retrieval by default for intelligent reasoning mode when a factual or domain-specific knowledge-base question requires retrieval.
- Optimize the reasoning prompt to borrow Weknora's Assess-Reconnaissance-Plan-Execute pattern while preserving this project's safety rules, event model, and tool names.
- Strengthen `grep_chunks` as a model-facing retrieval tool so LLM-generated synonyms, aliases, English names, legacy names, and abbreviations are captured in validated arguments.
- Remove domain-specific query expansion, intent keyword lists, answer-template branches, and post-retrieval constraint regexes from the retrieval path; the runtime executes a generic model-authored plan instead of accumulating per-question rules.
- Require mandatory deep reading after `grep_chunks` or `knowledge_search` returns candidates before factual answers are allowed.
- Add public trace metadata for search planning, grep execution, deep reading, reflection, and final synthesis without exposing hidden chain-of-thought, raw prompts, internal IDs, or tool parameters to end users.
- Keep quick mode fast and bounded; quick mode does not default to this model-driven grep-first loop unless a later change explicitly enables it.

## Capabilities

### New Capabilities

- `reasoning-llm-grep-first-retrieval`: Defines default intelligent-reasoning behavior for LLM-generated grep-first search planning, structured grep arguments, mandatory deep reading, prompt policy, trace visibility, and fallback behavior.

### Modified Capabilities

- None.

## Impact

- Affected backend services: `backend/app/services/agent_runtime.py`, `backend/app/services/agent_runtime_tools.py`, `backend/app/services/query_understanding.py`, `backend/app/services/rag_service.py`, `backend/app/models/agent_runtime.py`, and related runtime policy/config wiring in `backend/app/main.py`.
- Affected prompts: `backend/config/prompt_templates/agent_system_prompt.yaml`, especially the `progressive_rag_agent` policy.
- Affected retrieval behavior: reasoning mode will prefer `grep_chunks` before semantic expansion for KB factual questions, then deep-read candidate evidence before final synthesis.
- Affected observability: reasoning traces and tool events should expose safe summaries of search planning and evidence coverage, not private model reasoning or implementation details.
- No vector-store schema, document parsing, ingest, frontend API route, or SSE compatibility breaking change is intended.
