c## Context

Bee already has the ingredients for Weknora-like quick answers: query understanding, hybrid dense/keyword retrieval, optional rerank, parent recall, source extraction, a prompt catalog, SSE streaming, and a frontend agent timeline. The current quick chat path still wires those pieces as a direct Raw RAG shortcut: `_stream_raw_chat_events()` retrieves hits, emits `sources`, emits one `reasoning` summary, optionally emits one `AnalyzeQuestion` trace from `build_chat_agent_trace()`, and then streams `stream_answer()`.

That shortcut explains the user's screenshots. Bee can answer from the knowledge base, but the quick-mode timeline does not show separate public stages for understanding, retrieval, document citation, synthesis, and completion. Answer synthesis also only has special guidance for decision and how-to questions, so compatibility questions such as "可适配万兆堆叠线缆的交换机" can degrade into a flat list instead of Weknora-style Markdown with complete/partial compatibility and technical parameters.

The Weknora reference should be adapted, not ported. Weknora distinguishes Quick Q&A as RAG and Intelligent Reasoning as ReAct Agent. Bee should keep that same product distinction: quick stays fast and bounded; reasoning mode remains the place for open-ended runtime tools.

## Goals / Non-Goals

**Goals:**

- Make quick mode show a public, auditable RAG execution process similar to Weknora: question understanding, knowledge-base retrieval, evidence reading/citation preparation, synthesis, and completion.
- Reuse the existing retrieval, prompt catalog, SSE protocol, and frontend timeline normalizer.
- Improve source-grounded Markdown synthesis for product compatibility, adapter/support, and technical-parameter questions.
- Preserve quick-mode latency by avoiding open-ended ReAct loops and unbounded secondary reads.
- Keep hidden chain-of-thought private; the "思考" step is a public evidence-organization summary only.
- Add tests that catch regressions in trace shape, event order, answer guidance, and insufficient-evidence handling.

**Non-Goals:**

- Do not switch quick mode to `AgentRuntime`, ReAct, web search, MCP tools, or long tool loops.
- Do not expose private scratchpads, raw prompts, memory context, provider payloads, or hidden reasoning.
- Do not replace the existing frontend timeline with a new UI system.
- Do not change retrieval index storage, Milvus schema, parser behavior, or chunking fallback order.
- Do not require a new dependency or import Weknora code directly.

## Decisions

### Decision: Add a Quick Answer Workflow inside the existing Raw RAG path

Quick mode will keep using the direct retrieval-answer path, but the backend will structure it as a small deterministic workflow:

```text
UnderstandQuestion
  -> RetrieveKnowledgeBase
  -> ReadEvidence
  -> SynthesizeAnswer
  -> Complete
```

The workflow can be implemented as a helper on `RAGService` or a small service owned by `RAGService`. It should accept the question, scope, hits, retrieval debug metadata, sources, and context summary, then return public trace events. `_stream_raw_chat_events()` remains the route-level owner of SSE order.

Alternative considered: route quick mode through `AgenticRetrievalWorkflow`. That would show more steps, but it changes the semantics of "quick" and may add latency or graph/tool requirements. The quick workflow should be deterministic and bounded.

### Decision: Emit additive timeline-compatible events

Quick mode should continue emitting:

```text
sources
reasoning
agent_trace...
token...
[DONE]
```

The added `agent_trace` events should use safe stage names and metadata that the existing frontend normalizer can map without breaking old clients. If the frontend needs clearer labels, add aliases for the new stage names in `agent-stream.ts`; do not change the SSE envelope.

Expected public stage summaries:

- `UnderstandQuestion`: normalized query, selected knowledge-base scope, and applied terminology count.
- `RetrieveKnowledgeBase`: retrieval query count, top-k/candidate count, and whether dense, keyword, rerank, or fallback contributed.
- `ReadEvidence`: cited document count, selected chunk count, and matched source identifiers.
- `SynthesizeAnswer`: public summary that evidence is being organized into a grounded answer.
- `Complete`: final status, elapsed time if available, cited document count, and insufficient-evidence flag when applicable.

Alternative considered: emit Weknora-native frontend event names. That would force a bigger frontend contract change and duplicate existing normalization.

### Decision: Treat "thinking" as evidence organization, not model chain-of-thought

The quick timeline may show "思考", but its payload must be a public audit statement such as "根据已检索证据整理兼容系列和参数". It must not include chain-of-thought, scratchpads, raw prompts, or private model deliberation.

Alternative considered: stream model reasoning. This is unsafe and inconsistent with the existing project rule that visible traces are audit summaries.

### Decision: Add a compatibility/parameter answer style classifier

`RAGService._build_answer_style_guidance()` should recognize product compatibility and technical-parameter questions using conservative domain markers such as:

- Chinese: `适配`, `兼容`, `支持哪些`, `支持哪几`, `认证方式`, `业务端口`, `接入速率`, `技术参数`, `工作温度`, `传输速率`
- English: `compatible`, `support`, `adapter`, `spec`, `parameter`

When matched, the prompt guidance should require Markdown that is still fully source-grounded:

- Start with a direct conclusion.
- Use a table for fully supported or completely compatible series when the evidence supports it.
- Add a separate "部分型号适配系列" table only when the evidence distinguishes partial support.
- Add a "线缆技术参数" or equivalent parameter section only when the retrieved context contains those values.
- State "根据提供的文档无法确定" for unsupported details instead of inventing data.

Alternative considered: hardcode product-specific templates for the user's current switch/ONU corpus. That would overfit one data set and make future knowledge bases worse.

### Decision: Keep evidence expansion bounded

Quick mode should use existing parent recall and nearby context expansion. It may add a bounded "read evidence" summary over the same selected hits and matched child IDs, but it should not fetch arbitrary additional documents unless retrieval debug indicates low recall and existing low-recall expansion is enabled.

Alternative considered: mandatory deep-read tool calls like reasoning mode. That gives richer traces but blurs quick versus reasoning mode and can increase latency.

## Risks / Trade-offs

- [Risk] More quick trace events may make the UI look like reasoning mode. -> Mitigation: label it as a RAG execution process and keep tool counts at zero unless actual tools run.
- [Risk] Answer formatting guidance can make the model invent sections. -> Mitigation: require sections only when evidence supports them and add tests for insufficient-evidence wording.
- [Risk] Compatibility classification can false-positive on unrelated questions. -> Mitigation: use conservative markers and fall back to the existing default style when uncertain.
- [Risk] Extra event emission can duplicate the legacy reasoning panel. -> Mitigation: keep `reasoning` as compact retrieval details and let the timeline be the primary public process.
- [Risk] Chinese prompt text can suffer encoding drift. -> Mitigation: keep prompt-bearing files UTF-8 and cover with existing UTF-8 integrity tests.

## Migration Plan

1. Add tests describing quick trace event order and compatibility answer guidance before changing behavior.
2. Introduce a bounded quick trace builder that emits the five public stages from existing retrieval/debug data.
3. Wire `_stream_raw_chat_events()` to emit the richer trace while preserving `sources`, `reasoning`, and token streaming order.
4. Add compatibility/parameter guidance to `_build_answer_style_guidance()` or the prompt catalog.
5. Update frontend labels only if the existing normalizer does not display the new stage names clearly.
6. Update design docs and run backend unit tests plus frontend build/normalizer tests.

Rollback is configuration-safe: if `AGENT_TRACE_STREAM_ENABLED=false`, quick mode still streams sources, reasoning, and answer tokens. If the new answer guidance causes regressions, disable or narrow the classifier without changing retrieval.

## Open Questions

- Should quick-mode "ReadEvidence" emit synthetic `tool_call`/`tool_observation` events for visual parity, or only `agent_trace` stages to avoid implying actual tools ran?
- Should the frontend collapsed summary say "调用 0 次工具" for quick RAG, or use a different summary such as "检索 N 次 · 引用 N 篇文档"?
- Should generated suggested questions and quick-answer guidance share the same topic classifier later, or remain independent?
