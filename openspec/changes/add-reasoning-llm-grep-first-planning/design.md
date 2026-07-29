## Context

The backend already has a Weknora-style reasoning runtime: `AgentRuntime` receives model tool calls, validates them through `ToolRegistry`, executes read-only RAG tools, streams public agent events, and enforces a deep-read guard before factual answers. The current `progressive_rag_agent` prompt tells the model to anchor exact terms with `grep_chunks`, but it does not make LLM-generated grep-first planning the default first retrieval move for intelligent reasoning.

The Weknora reference prompt shows the important pattern: the model uses its parametric language and domain knowledge during the first model call to generate a synonym-rich `grep_chunks` argument, then the system executes that query and forces full-content reading before answer synthesis. This project should adapt that behavior without copying product identity, web defaults, citation tag syntax, FAQ-specific IDs, or storage-specific assumptions.

Current constraints:

- Reasoning mode is the correct default surface for model-driven tool use; quick mode must remain fast and bounded.
- The backend must keep knowledge-base scope isolation and existing SSE compatibility.
- Tool traces are public audit summaries, not hidden chain-of-thought.
- Facts in final answers must come from retrieved and deep-read evidence, not from the LLM-generated synonyms themselves.

## Goals / Non-Goals

**Goals:**

- Make intelligent reasoning mode default to grep-first retrieval for factual or domain-specific KB questions.
- Use the LLM's tool-call arguments to capture synonyms, aliases, abbreviations, English names, legacy names, product names, and time/action variants.
- Upgrade the `grep_chunks` model-facing contract so structured multi-query arguments are executable and testable.
- Preserve mandatory deep reading after search tools return candidates.
- Optimize `progressive_rag_agent` with an Assess-Reconnaissance-Plan-Execute workflow adapted to Bee.
- Make product/spec lookup questions produce evidence-grounded selection advice when the retrieved evidence supports multiple candidates or distinguishable scenarios.
- Keep query planning and answer synthesis domain agnostic so new domains do not require application-code keyword lists, terminology files, or attribute-specific regexes.
- Emit user-safe trace events for search planning, retrieval, deep reading, reflection, and synthesis.

**Non-Goals:**

- Do not make quick mode default to open-ended model-driven retrieval.
- Do not rely on a hand-maintained terminology dictionary as the primary synonym source.
- Do not add per-domain query expansion, intent classification, answer formatting, or candidate filtering branches to the deterministic runtime.
- Do not answer from LLM-generated search terms unless retrieved evidence supports the claim.
- Do not expose raw prompts, private reasoning, internal IDs, raw tool arguments, or provider payloads to end users.
- Do not change vector-store schema, ingest, parser behavior, document chunking, or frontend route contracts.
- Do not introduce web search as a default fallback in this change.

## Decisions

### Decision 1: Reasoning mode defaults to LLM-driven grep-first

When `AGENT_RUNTIME_ENABLED=true` and the active chat policy is `reasoning`, factual or domain-specific KB questions should begin with `grep_chunks` unless retrieval is unnecessary. The model may answer directly only for conversational messages, visible image-only descriptions, or non-KB creative/editing tasks.

Rationale: this matches the Weknora mechanism the user identified. The useful synonym expansion is in the LLM's `tool_calls.function.arguments`, not in a static dictionary.

Alternative considered: keep the current prompt language as a soft preference. That leaves behavior under-specified and allows the model to jump directly to semantic search or final answers.

### Decision 2: Use prompt policy plus runtime guard

The prompt should strongly instruct the model that the first KB retrieval action is `grep_chunks`. The runtime should also enforce a guard: when a reasoning request appears to require KB factual evidence and the model tries to answer or semantically search before any grep attempt, the runtime appends a corrective message and continues within the existing iteration limit.

Rationale: prompt-only control is brittle. A lightweight guard keeps behavior consistent without hardcoding synonyms.

Alternative considered: force `tool_choice` to `grep_chunks` for the first model call. That is deterministic but too rigid for non-retrieval questions and for future reasoning policies.

### Decision 3: One packed alternation call is the prompt default, structured arguments remain supported

For the common case, the prompt should prefer one packed grep call per search objective: choose the 2-3 highest-value alternatives and pass them as one simple `term1|term2|term3` query. This reduces repeated tool calls while preserving provider-safe alternation normalization.

`grep_chunks` should also accept a structured shape when genuinely distinct hard constraints cannot be represented by one packed query:

```json
{
  "queries": ["risk control system", "risk control platform", "Enterprise Risk"],
  "required_terms": ["launch", "go live", "release"],
  "top_k": 12,
  "match_mode": "any_query"
}
```

The tool execution layer should normalize both forms into bounded search variants. If the model provides `query: "A|B|C"`, the backend may split simple alternation into variants for SQLite FTS/BM25 providers that do not implement regex OR semantics.

Rationale: Weknora can depend on regex-capable grep. This project currently passes normalized variants to `keyword_retrieve_hits`, where `|` may not behave as OR for every provider. A packed model-facing query encourages one-call recall, while normalization and optional structured fields preserve reliable execution.

Alternative considered: keep only regex-like strings. That looks familiar to the model but can silently under-recall when the keyword backend treats the string literally.

### Decision 4: Deep read remains the evidence gate

After `grep_chunks` or `knowledge_search` returns candidates, reasoning mode must call `list_knowledge_chunks` or `get_document_info` before a factual final answer is accepted. Search snippets and LLM-generated terms are only pointers.

Rationale: grep-first improves recall, but it does not prove the answer. The final answer must be grounded in full evidence.

Alternative considered: allow final answers from high-confidence grep snippets. That would be faster but would weaken evidence quality and contradict the existing runtime guard.

### Decision 5: Prompt structure follows Weknora while project-specific contracts remain truthful

The `progressive_rag_agent` prompt should follow Weknora's complete Assess-Reconnaissance-Plan-Execute structure:

```text
Role: Bee, an evidence-first retrieval assistant for isolated knowledge bases.

Workflow:
Intent Assessment
-> Phase 1: grep_chunks + knowledge_search reconnaissance
-> mandatory Deep Read
-> Phase 2: direct answer or work plan
-> Phase 3: sequential search, Deep Read, reflection, and gap repair
-> Phase 4: final synthesis with no tool calls

Strict retrieval sequence:
packed grep alternation -> semantic expansion -> full-content Deep Read
```

Rationale: the useful behavior is Weknora's full retrieval discipline and phase structure. Bee identity, storage behavior, tool schemas, Web availability, and source rendering still need to describe this project accurately.

Alternative considered: paste every Weknora-specific sentence verbatim. That would incorrectly claim Tencent identity, FAQ-only parameters, PostgreSQL POSIX regex behavior, and unsupported inline citation tags.

### Decision 6: Trace shows safe planning summaries

Reasoning traces should expose safe summaries such as generated query count, selected search strategy, matched document count, candidate count, deep-read count, and evidence sufficiency. The UI-facing trace should not show raw internal IDs or full raw tool arguments; detailed IDs can remain in backend metadata where existing systems need them for citation verification.

Rationale: users need to trust the retrieval process without seeing internal plumbing or private model reasoning.

Alternative considered: expose full `tool_calls.arguments`. That is helpful for debugging but violates the current user-friendly communication boundary and can leak internal strategy.

### Decision 7: Constraint evaluation is model-authored and domain agnostic

For filtering, comparison, and recommendation requests, the model extracts entities, requested relations or actions, hard constraints, aliases, units, operators, and thresholds. It then generates retrieval variants and verifies each constraint against deep-read evidence for the same candidate or subject. Application code does not classify these requests with domain keyword lists or remove candidates using attribute-specific regexes.

Rationale: domain semantics belong in the LLM-authored tool arguments and evidence synthesis. The deterministic runtime should validate bounded schemas, enforce retrieval/deep-reading order, and preserve evidence provenance.

Alternative considered: add a parser and post-retrieval filter for every new product family or parameter type. That causes rule accumulation, misses unseen terminology, and can discard valid evidence before the model evaluates it.

## Risks / Trade-offs

- [Risk] The model may over-expand with unrelated synonyms. -> Mitigation: bound query counts, cap output size, record matched queries, and rely on deep-read evidence before synthesis.
- [Risk] Removing deterministic domain filters can retain more distractor candidates. -> Mitigation: require per-candidate evidence ledgers, same-subject provenance, and explicit unresolved verdicts during final synthesis.
- [Risk] Grep-first can add latency in reasoning mode. -> Mitigation: keep it reasoning-only by default, limit max tool calls, and reuse existing iteration limits.
- [Risk] Regex-like input may not execute consistently across keyword providers. -> Mitigation: normalize structured `queries` and split simple alternation before provider calls.
- [Risk] A strict guard may frustrate non-retrieval reasoning. -> Mitigation: apply it only when the request appears to require KB factual/domain evidence and a KB scope is available.
- [Risk] Prompt changes can regress existing agent behavior. -> Mitigation: add tests for first-tool preference, deep-read guard, final answer behavior, and prompt confidentiality.
- [Risk] Public traces can reveal too much implementation detail. -> Mitigation: use sanitized summaries and the existing `scrub_private_fields` boundary.

## Migration Plan

1. Add config fields for reasoning grep-first defaults while keeping rollback flags.
2. Extend `grep_chunks` schema and execution normalization while preserving existing `query` compatibility.
3. Add runtime state tracking for first grep attempt and a guard for KB factual reasoning requests.
4. Update `progressive_rag_agent` with the adapted Assess-Reconnaissance-Plan-Execute prompt.
5. Add product/spec lookup answer guidance for evidence-grounded selection advice.
6. Add backend tests for structured grep arguments, regex-style compatibility, first-retrieval guard, mandatory deep-read, prompt guidance, and trace sanitization.
7. Update `docs/design-docs/backend-rag-pipeline.md` with the reasoning-mode retrieval and answer synthesis behavior.

Rollback: disable the new reasoning grep-first config flag or select a previous prompt template id. Existing quick mode and deterministic fallback paths remain available.

## Open Questions

- Should the first grep guard be enabled for all reasoning KB questions, or only for route/intents classified as factual, source, how-to, troubleshooting, comparison, impact, dependency, summary, or decision?
- Should sanitized trace summaries show representative search terms, or only counts and document names?
- Should quick mode later use the same planner only on low-recall retrieval misses?
