## ADDED Requirements

### Requirement: Model-owned ReAct action selection
For every reasoning round, the runtime SHALL treat the tool-enabled LLM inference as the ReAct `Think` phase and SHALL let that inference decide whether retrieval is needed and choose between a grounded final answer and zero or more registered tool calls. The controller SHALL limit choices through tool availability, authorization, evidence guards, and budgets, but SHALL NOT use keyword or regular-expression heuristics to pre-plan the first action or prescribe a fixed sequence of retrieval, reflection, and reading actions. The optional `thinking` tool SHALL NOT be a prerequisite for selecting or invoking another tool.

#### Scenario: Model selects multiple retrieval actions
- **WHEN** the LLM returns valid calls to `grep_chunks` and `knowledge_search` in one response
- **THEN** the runtime accepts both calls as one action batch without forcing either call into a separate model round

#### Scenario: First Think phase directly selects grep
- **WHEN** the first tool-enabled LLM inference determines that knowledge-base retrieval is needed
- **THEN** it can directly return `grep_chunks` with generated query variants without first returning a `thinking` tool call

#### Scenario: Think phase determines retrieval is unnecessary
- **WHEN** the first tool-enabled LLM inference determines that the request is conversational or otherwise needs no external evidence
- **THEN** it can return a final answer without the controller forcing grep from lexical characteristics of the user text

#### Scenario: Model changes strategy after observation
- **WHEN** the LLM observes that an earlier search did not cover a required concept
- **THEN** the LLM can choose a different query or retrieval tool in the next round without a controller-generated synonym list or fixed retry recipe

### Requirement: First retrieval batch includes lexical grep
When the LLM chooses knowledge-base retrieval under grep-first policy, the runtime SHALL require at least one `grep_chunks` call in the first batch that contains a retrieval action. The policy SHALL permit independent semantic or graph retrieval calls in that same batch and SHALL NOT independently classify retrieval necessity from the wording of the user question.

#### Scenario: Grep and semantic search share the first batch
- **WHEN** the first retrieval response contains `grep_chunks` and `knowledge_search`
- **THEN** the runtime accepts the batch because grep is present

#### Scenario: First retrieval batch omits grep
- **WHEN** the first retrieval response contains only retrieval tools other than `grep_chunks`
- **THEN** the runtime rejects or corrects the batch through the existing policy guard and records a machine-readable policy reason

### Requirement: LLM-generated query variants remain request-local
The reasoning prompt SHALL instruct the LLM to generate useful synonyms, aliases, abbreviations, translations, model-name fragments, and parameter expressions directly in tool arguments when they improve recall. The runtime SHALL NOT require a pre-generated synonym dictionary or a separate synonym-generation stage.

#### Scenario: Synonyms are emitted with the tool call
- **WHEN** the user asks about a concept that may have multiple names
- **THEN** the LLM can include those variants in the same `grep_chunks` query or semantic query list used for retrieval

#### Scenario: Later evidence suggests another alias
- **WHEN** an observation reveals a previously unknown product family or domain alias
- **THEN** the LLM can use that alias in a later tool call without persisting it to a global dictionary

### Requirement: Validated same-round tool batching
The runtime SHALL parse and validate every tool call in a model response before starting the batch. It SHALL classify registered tools by execution safety and SHALL execute independent `parallel_safe` calls with bounded concurrency while preserving `serial` or `exclusive` execution constraints.

#### Scenario: Independent tools execute concurrently
- **WHEN** one model response contains two valid independent calls classified as `parallel_safe` and the worker limit is at least two
- **THEN** both calls execute concurrently and the runtime waits for the whole batch before starting the next model round

#### Scenario: Stateful tool remains serialized
- **WHEN** a batch contains a tool classified as `serial` or `exclusive`
- **THEN** the runtime executes it according to its declared constraint without overlapping an unsafe call

#### Scenario: One call is invalid
- **WHEN** any tool call has an unknown name, invalid arguments, or violates request scope
- **THEN** the runtime returns a structured observation for that call and SHALL NOT bypass validation to execute it

### Requirement: Deterministic batch observations
The runtime SHALL append tool observations to model history and emit public tool events in the original model-declared call order, regardless of physical completion order. A failed call SHALL be isolated to its own observation unless policy requires the whole batch to stop.

#### Scenario: Calls finish out of order
- **WHEN** the second call completes before the first call
- **THEN** the next model turn receives observations ordered by the original call indexes

#### Scenario: One independent call fails
- **WHEN** one call in a parallel-safe batch fails and another succeeds
- **THEN** the runtime exposes both the structured failure and successful result to the next model round without discarding the successful evidence

### Requirement: Race-free request state
Concurrent tool workers SHALL NOT mutate shared runtime state or shared retrieval-debug fields directly. Each tool SHALL return a result plus a request-scoped state delta, and the controller SHALL merge accepted deltas deterministically in original call order.

#### Scenario: Parallel searches update candidates
- **WHEN** parallel grep and semantic searches return overlapping candidate identifiers
- **THEN** the controller merges them into request state deterministically using the defined de-duplication and ordering rules

#### Scenario: Retrieval debug data is concurrent
- **WHEN** two retrieval tools execute concurrently
- **THEN** each result retains its own debug metadata and neither call overwrites the other call's metadata

### Requirement: Evidence-driven deep reading
Search-result metadata SHALL be treated as candidate discovery rather than answer evidence. When selected candidates contain the evidence needed for an answer, the LLM SHALL request full chunk or document content in a subsequent action after observing candidate identifiers. The runtime SHALL block an unsupported final answer when mandatory deep-read evidence has not been obtained.

#### Scenario: Search returns candidate identifiers
- **WHEN** the first retrieval batch returns matching chunks or documents
- **THEN** the next model round can choose one or more full-content read calls using the observed identifiers

#### Scenario: Model tries to answer from search summaries only
- **WHEN** mandatory deep-read policy applies and the LLM returns a final factual answer without reading qualifying full content
- **THEN** the runtime rejects the terminal answer and returns a guard observation without selecting a read target on the model's behalf

#### Scenario: Evidence is already deeply read
- **WHEN** qualifying full content is present and answer sufficiency guards pass
- **THEN** the LLM can finish without an additional retrieval action

### Requirement: Autonomous gap remediation
The default reasoning path SHALL treat reflection status, evidence gaps, and corrected queries as observations for the LLM. A `thinking` result SHALL NOT automatically trigger controller-selected search or deep-read calls. Any legacy controller-remedial path SHALL require an explicit disabled-by-default compatibility flag.

#### Scenario: Thinking reports an evidence gap
- **WHEN** `thinking` returns a gap and a proposed correction query without co-issued retrieval calls
- **THEN** the runtime presents that observation to the next LLM round and does not invoke retrieval automatically

#### Scenario: Model co-issues reflection and correction
- **WHEN** the LLM returns a public `thinking` audit summary together with an independent corrective retrieval call
- **THEN** the runtime processes them within the same action batch subject to tool safety classification

#### Scenario: Legacy remediation is enabled
- **WHEN** an operator explicitly enables the compatibility flag
- **THEN** the runtime may use the legacy remedial behavior and records that non-default policy in trace metadata

### Requirement: Public reasoning remains concise and safe
Any user-visible `thinking` content SHALL be a concise audit summary of intent, evidence status, or the next action and SHALL NOT expose private chain-of-thought, hidden prompts, credentials, or raw internal messages. The runtime SHALL NOT require a standalone `thinking` call solely to advance the loop.

#### Scenario: Audit summary is emitted
- **WHEN** the model uses the `thinking` tool
- **THEN** the user-visible event contains only a short status summary suitable for the activity timeline

#### Scenario: Direct retrieval is sufficient
- **WHEN** the model can choose the next retrieval action directly
- **THEN** the runtime accepts the retrieval calls without first requiring a `thinking` tool call

### Requirement: Bounded autonomous execution
The runtime SHALL enforce configurable per-request limits for action rounds, total LLM calls, total tool calls, parallel workers, and wall-clock duration. Defaults SHALL treat action-round count as a safety ceiling rather than a target and SHALL reserve capacity for terminal synthesis.

#### Scenario: Tool-call budget would be exceeded
- **WHEN** a proposed batch would exceed the remaining tool-call budget
- **THEN** the runtime refuses excess calls deterministically, records the budget reason, and proceeds to an allowed terminal path

#### Scenario: Wall-clock budget expires
- **WHEN** request execution reaches its wall-clock limit
- **THEN** the runtime stops scheduling new actions and proceeds to terminal synthesis or evidence-insufficient fallback

### Requirement: Reliable terminal synthesis
The runtime SHALL finish normally when the LLM returns no tool calls, returns answer content, and all answer guards pass. If the action-round limit or another recoverable budget is reached after qualifying evidence has been read, the runtime SHALL perform one reserved tools-disabled synthesis call over the accumulated evidence. It SHALL use a deterministic evidence-insufficient fallback only when grounded synthesis is impossible.

#### Scenario: Model returns a valid final answer
- **WHEN** the LLM returns content without tool calls and evidence guards pass
- **THEN** the runtime emits that content as the final answer and exits the loop

#### Scenario: Action limit reached with evidence
- **WHEN** no action rounds remain and qualifying deep-read evidence exists
- **THEN** the runtime invokes one tools-disabled final synthesis and emits its grounded result

#### Scenario: Action limit reached without evidence
- **WHEN** no action rounds remain and no qualifying answer evidence exists
- **THEN** the runtime emits the localized evidence-insufficient fallback without inventing facts

### Requirement: Repeated-action loop detection
The runtime SHALL compute a normalized signature from each batch's ordered tool names and canonicalized arguments. It SHALL stop rescheduling when an equivalent signature repeats beyond the configured threshold without material new evidence.

#### Scenario: Same search repeats without new evidence
- **WHEN** the LLM repeats the same normalized retrieval batch and observations add no material evidence
- **THEN** the runtime records a stuck-loop reason and enters the terminal path

#### Scenario: Similar tool uses different material arguments
- **WHEN** the LLM calls the same tool with a materially different query or candidate identifier
- **THEN** the runtime treats it as a distinct action signature

### Requirement: Provider-compatible parallel tool calling
The model adapter SHALL expose a provider capability for multiple tool calls and SHALL request parallel tool calling explicitly only when supported. Unsupported or rejected provider options SHALL degrade to compatible model invocation and safe serial tool execution without changing answer correctness.

#### Scenario: Provider supports parallel tool calls
- **WHEN** the configured provider declares parallel tool-call support
- **THEN** the adapter enables the provider option and accepts multiple calls from one response

#### Scenario: Provider rejects the option
- **WHEN** the provider rejects the parallel tool-call parameter as unsupported
- **THEN** the adapter retries using the compatible request shape, records the fallback, and continues without exposing a server error to the user

### Requirement: Streaming and latency observability
The runtime SHALL preserve the existing agent-domain-event and SSE ordering contracts while emitting batch-aware progress. It SHALL record model latency, action-round duration, tool queue and execution duration, batch wall time, terminal first-token latency, fallback reason, and configured budget values. When terminal streaming is supported, answer tokens SHALL be forwarded incrementally.

#### Scenario: Parallel batch is displayed
- **WHEN** a model round starts multiple tool calls
- **THEN** tool lifecycle events retain stable call identifiers and the round does not complete until every scheduled call has reached a terminal state

#### Scenario: Final synthesis streams
- **WHEN** the provider supports terminal response streaming
- **THEN** answer token events are emitted as text arrives while the final event remains last

#### Scenario: Latency trace is inspected
- **WHEN** a request completes
- **THEN** its trace distinguishes time spent waiting on model rounds from tool execution and reports whether batching, provider fallback, or budget termination occurred

### Requirement: Behavioral and performance verification
Automated tests SHALL verify action autonomy, batch validation, bounded concurrency, deterministic merge and event ordering, deep-read enforcement, loop detection, terminal synthesis, provider fallback, and compatibility with existing streaming consumers. A timing test using controlled tool delays SHALL demonstrate overlap for parallel-safe calls without depending on external services.

#### Scenario: Concurrency timing test
- **WHEN** two parallel-safe fake tools each block for a controlled duration
- **THEN** measured batch wall time demonstrates overlap within a documented tolerance and observations remain deterministically ordered

#### Scenario: Existing SSE consumer processes a batched run
- **WHEN** a run includes a multi-tool batch and streamed terminal answer
- **THEN** the existing frontend event consumer completes the timeline and answer without duplicate, missing, or permanently-running steps
