## 1. Runtime Configuration

- [x] 1.1 Add reasoning grep-first configuration fields to `AgentRuntimeConfig` with reasoning default enabled and quick default disabled.
- [x] 1.2 Wire the new environment variables in `backend/app/main.py` and document their defaults.
- [x] 1.3 Extend `ChatRuntimePolicy` or policy resolution so reasoning policies can distinguish grep-first enforcement from generic tool availability.

## 2. Grep Tool Contract

- [x] 2.1 Extend `GrepChunksTool.parameters` to accept structured `queries`, `required_terms`, `match_mode`, and `top_k` while preserving the legacy `query` field.
- [x] 2.2 Implement argument normalization for structured queries, simple alternation strings, empty values, bounds, and unsupported match modes.
- [x] 2.3 Execute normalized grep variants through existing keyword retrieval, deduplicate by chunk id, preserve matched query metadata, and return bounded observations.
- [x] 2.4 Add recoverable error handling for invalid grep arguments without breaking the runtime stream.

## 3. Reasoning Runtime Guard

- [x] 3.1 Track whether a reasoning run has performed KB grep-first retrieval before semantic-only retrieval or final answer.
- [x] 3.2 Detect factual/domain KB questions conservatively enough to apply the guard only when retrieval is required.
- [x] 3.3 Add a corrective runtime message when the model skips required grep-first retrieval.
- [x] 3.4 Preserve the existing mandatory deep-read guard after `grep_chunks` or `knowledge_search` returns candidates.

## 4. Prompt Optimization

- [x] 4.1 Rewrite the `progressive_rag_agent` prompt in `backend/config/prompt_templates/agent_system_prompt.yaml` around the adapted Assess-Reconnaissance-Plan-Execute workflow.
- [x] 4.2 Add explicit first-retrieval guidance requiring `grep_chunks` for factual KB questions and instructing the model to include aliases, synonyms, abbreviations, English names, legacy names, product names, and time/action variants in grep arguments.
- [x] 4.3 Preserve Bee identity, knowledge-base isolation, fresh retrieval per turn, mandatory deep reading, prompt confidentiality, and user-friendly communication constraints.
- [x] 4.4 Avoid copying unsupported Weknora-specific details such as Tencent branding, FAQ-only IDs, storage-specific regex guarantees, web-default fallback, or unsupported inline citation tag syntax.
- [x] 4.5 Add domain-agnostic multi-constraint final-answer guidance for filtering, comparison, and recommendation requests.
- [x] 4.6 Remove static terminology loading, domain-specific query expansion, intent/format branches, and attribute-specific retrieval filters from the default path.

## 5. Trace And Observability

- [x] 5.1 Add safe trace metadata for grep-first planning, grep execution, candidate counts, document counts, deep-read counts, and evidence sufficiency.
- [x] 5.2 Ensure user-visible trace summaries omit hidden reasoning, raw prompts, secrets, raw internal IDs, and unbounded tool arguments.
- [x] 5.3 Preserve existing SSE compatibility events for reasoning mode.

## 6. Tests

- [x] 6.1 Add unit tests for structured `grep_chunks` argument validation and normalization.
- [x] 6.2 Add unit tests for legacy alternation query compatibility.
- [x] 6.3 Add runtime tests proving reasoning factual KB questions are corrected when the first model response skips required grep-first retrieval.
- [x] 6.4 Add runtime tests proving final factual answers remain blocked until candidates are deep-read.
- [x] 6.5 Add prompt/template tests for required grep-first instructions and prompt confidentiality constraints.
- [x] 6.6 Add trace sanitization tests for search planning and tool events.
- [x] 6.7 Add answer-guidance tests for domain-agnostic multi-constraint evidence evaluation.
- [x] 6.8 Add regression tests proving unseen domains use the same guidance and LLM-authored query variants without static dictionaries.

## 7. Documentation And Validation

- [x] 7.1 Update `docs/design-docs/backend-rag-pipeline.md` with reasoning-mode LLM-driven grep-first behavior.
- [x] 7.2 Update `docs/DEVELOPMENT.md` if new validation commands or environment variables are introduced.
- [x] 7.3 Run the relevant backend tests from `docs/DEVELOPMENT.md`.
- [x] 7.5 Update OpenSpec design/spec notes for evidence-grounded product selection advice.
- [ ] 7.4 Manually smoke-test reasoning mode with a question like "风控系统什么时候上线的？" and verify grep-first, deep read, sources, and insufficient-evidence behavior.
