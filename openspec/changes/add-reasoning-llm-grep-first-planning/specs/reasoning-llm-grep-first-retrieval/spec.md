## ADDED Requirements

### Requirement: Reasoning Mode Defaults To Grep-First KB Retrieval
When intelligent reasoning mode handles a factual or domain-specific question with an available knowledge-base scope, the system SHALL make LLM-driven `grep_chunks` the default first knowledge-base retrieval action unless retrieval is unnecessary for the request.

#### Scenario: Factual KB question starts with grep
- **WHEN** a user asks a reasoning-mode question such as "When did the risk control system go live?" and the request is bound to a knowledge base
- **THEN** the runtime MUST allow the model to generate a `grep_chunks` tool call before semantic-only retrieval or final answer synthesis

#### Scenario: Conversational request bypasses retrieval
- **WHEN** a user sends a greeting, thanks, farewell, or purely conversational message in reasoning mode
- **THEN** the runtime SHALL allow a direct answer without requiring `grep_chunks`

#### Scenario: Direct final answer is guarded
- **WHEN** a reasoning-mode factual KB question receives a model response that tries to answer before any KB retrieval
- **THEN** the runtime MUST block that final answer, append a corrective instruction to run grep-first KB retrieval, and continue within the configured iteration limit

### Requirement: LLM Generated Grep Arguments Capture Search Variants
The reasoning prompt and tool schema SHALL instruct the model to use its parametric language and domain knowledge to include synonyms, aliases, abbreviations, English names, legacy names, product names, and time/action variants in `grep_chunks` arguments while treating those terms only as retrieval hints.

#### Scenario: Time question includes entity and time variants
- **WHEN** the user asks "风控系统什么时候上线的？"
- **THEN** the model-facing policy MUST encourage `grep_chunks` arguments that include variants such as system/platform/risk-control names and time terms such as go-live, launch, release, publish, or production

#### Scenario: Generated terms do not become facts
- **WHEN** the model generates a synonym or English alias in `grep_chunks` arguments
- **THEN** the final answer MUST NOT treat that generated term as evidence unless a retrieved and deep-read knowledge-base chunk supports the factual claim

### Requirement: GrepChunks Supports Structured Multi-Query Arguments
The `grep_chunks` runtime tool SHALL accept structured multi-query arguments in addition to the existing single `query` string and SHALL normalize both forms into bounded executable keyword searches.

#### Scenario: Structured queries execute as multiple keyword searches
- **WHEN** the model calls `grep_chunks` with `queries`, optional `required_terms`, `top_k`, and `match_mode`
- **THEN** the tool MUST validate and normalize the arguments, execute bounded keyword retrieval for the variants, deduplicate results by chunk identity, and return a safe observation summary

#### Scenario: Regex-style query remains compatible
- **WHEN** the model calls `grep_chunks` with a legacy single `query` value containing simple alternation such as `risk system|risk platform|Enterprise Risk`
- **THEN** the tool SHALL preserve compatibility by executing the intended alternatives even when the active keyword provider does not implement regex OR semantics

#### Scenario: Invalid grep arguments are rejected safely
- **WHEN** the model calls `grep_chunks` with non-string queries, too many variants, empty values, or unsupported match modes
- **THEN** the tool MUST coerce safe values where possible, reject unsafe values, and return a recoverable tool error without breaking the runtime stream

### Requirement: Search Results Require Deep Reading Before Factual Answers
When `grep_chunks` or `knowledge_search` returns candidate knowledge-base evidence in reasoning mode, the runtime MUST require `list_knowledge_chunks` or `get_document_info` to read full evidence before allowing a factual final answer.

#### Scenario: Search candidates trigger deep-read requirement
- **WHEN** `grep_chunks` returns one or more candidate chunks
- **THEN** the runtime MUST track those candidates and reject a factual final answer until full evidence has been deep-read

#### Scenario: Deep-read evidence permits synthesis
- **WHEN** the runtime has deep-read relevant chunks or document information for the candidates
- **THEN** the model MAY synthesize a final answer grounded in that evidence

#### Scenario: Missing evidence yields insufficient-evidence answer
- **WHEN** grep-first and subsequent allowed retrieval steps do not produce deep-read evidence that answers the question
- **THEN** the final response MUST clearly state that the knowledge base does not contain enough information instead of inventing the fact

### Requirement: Reasoning Prompt Uses Adapted Assess-Reconnaissance-Plan-Execute Policy
The `progressive_rag_agent` prompt SHALL be optimized around an adapted Assess-Reconnaissance-Plan-Execute workflow that fits Bee's tool set, scope model, privacy rules, and final answer standards.

#### Scenario: Prompt includes first retrieval discipline
- **WHEN** the prompt template is rendered for reasoning mode
- **THEN** it MUST tell the model that KB factual retrieval starts with `grep_chunks`, followed by semantic expansion when needed and mandatory deep reading before final synthesis

#### Scenario: Prompt preserves Bee identity and project constraints
- **WHEN** the prompt template is updated from the Weknora reference
- **THEN** it MUST identify the assistant as Bee for this project and MUST NOT copy unrelated product identity, FAQ-only parameter names, external web defaults, or unsupported citation tag requirements

#### Scenario: Prompt protects private instructions
- **WHEN** a user asks about system prompts, hidden workflow, tool parameters, or internal instructions
- **THEN** the prompt policy MUST instruct the model to provide only a high-level role description and not reveal or summarize confidential instructions

### Requirement: Product Spec Lookup Produces Grounded Selection Advice
When a user asks for product models by combining a selector with product and specification constraints, the system SHALL guide answer synthesis to include evidence-grounded selection advice when the retrieved and deep-read evidence supports it.

#### Scenario: Spec-filtered model lookup includes selection section
- **WHEN** the user asks a question such as "找出24个光口的交换机"
- **THEN** the answer guidance MUST classify the request as product selection, list matching candidate models first, and ask the model to add a "选型建议" section when candidate attributes support distinguishable scenarios

#### Scenario: Selection advice remains evidence grounded
- **WHEN** the answer includes "选型建议"
- **THEN** scenario labels, recommendation reasons, and model attributes MUST come from the same product or same source evidence, and unsupported scenario differences MUST be stated as unavailable rather than invented

### Requirement: Public Trace Summaries Are Safe And Auditable
The reasoning runtime SHALL emit public trace and tool events that summarize search planning, grep execution, deep reading, reflection, and final synthesis without exposing hidden reasoning or raw internal details.

#### Scenario: Search planning trace is visible without raw internals
- **WHEN** the model performs grep-first planning
- **THEN** the emitted trace SHOULD include safe metadata such as query count, matched document count, candidate count, and retrieval status while omitting raw prompts, hidden chain-of-thought, internal IDs, secrets, and unbounded tool arguments

#### Scenario: Tool event compatibility is preserved
- **WHEN** reasoning mode emits grep-first tool calls and observations
- **THEN** existing SSE-compatible `agent_trace`, `tool_call`, `tool_observation`, `sources`, `token`, and completion behavior SHALL remain backward compatible for current clients

### Requirement: Reasoning Grep-First Is Configurable With Safe Defaults
The system SHALL default reasoning grep-first behavior to enabled when the agent runtime is enabled, while providing configuration that can disable it without affecting quick mode or deterministic fallbacks.

#### Scenario: Reasoning default is enabled
- **WHEN** `AGENT_RUNTIME_ENABLED=true` and no explicit grep-first override is configured
- **THEN** reasoning mode SHALL use LLM-driven grep-first policy by default

#### Scenario: Quick mode remains bounded
- **WHEN** quick mode handles a request
- **THEN** it SHALL NOT default to the reasoning grep-first ReAct loop unless a separate quick-mode feature flag explicitly enables that behavior

#### Scenario: Rollback disables grep-first policy
- **WHEN** an operator disables the reasoning grep-first configuration
- **THEN** the runtime SHALL fall back to the previous reasoning prompt/tool behavior while preserving existing agent runtime operation
