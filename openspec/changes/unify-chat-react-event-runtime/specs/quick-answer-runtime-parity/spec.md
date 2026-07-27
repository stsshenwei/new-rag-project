## ADDED Requirements

### Requirement: Quick Mode Latency Preservation
Quick mode SHALL remain low-latency while using the shared runtime.

#### Scenario: Evidence-grounded quick answer
- **WHEN** a quick-mode request has sufficient preloaded knowledge-base evidence
- **THEN** the runtime SHALL complete without entering an open-ended multi-round tool loop

#### Scenario: Quick mode answer completes
- **WHEN** quick mode completes normally
- **THEN** the observed event sequence SHALL include query, references when available, final answer content, completion, and transport `[DONE]`

### Requirement: Quick Mode Preloaded Evidence
Quick mode SHALL use bounded preloaded retrieval evidence rather than model-driven open-ended retrieval by default.

#### Scenario: Retrieval returns sources
- **WHEN** quick policy retrieval returns source documents or chunks
- **THEN** the runtime SHALL include bounded evidence in the model context and emit compatible reference/source events before answer content

#### Scenario: Retrieval returns no sufficient evidence
- **WHEN** quick policy retrieval cannot find sufficient evidence
- **THEN** the runtime SHALL answer with an insufficient-evidence message instead of inventing unsupported facts

### Requirement: Quick Mode Does Not Use Remedial Loop By Default
Quick mode SHALL NOT run the reasoning-mode reflective remedial retrieval loop by default.

#### Scenario: Quick mode evidence has a gap
- **WHEN** quick mode cannot answer from preloaded evidence
- **THEN** the runtime SHALL complete with a concise insufficient-evidence answer unless an explicit quick fallback policy is configured

#### Scenario: Reasoning mode requested
- **WHEN** the user selects reasoning mode for the same question
- **THEN** the runtime MAY use reflection and bounded remedial retrieval according to reasoning policy

### Requirement: Quick And Reasoning Timeline Compatibility
Quick mode SHALL emit domain events that the frontend can render with the same timeline pipeline as reasoning mode.

#### Scenario: Quick event stream received
- **WHEN** the frontend receives quick-mode domain events
- **THEN** it SHALL normalize them through the same event parser and timeline builder used for reasoning mode

#### Scenario: Quick event stream lacks tool calls
- **WHEN** quick mode emits no tool call events
- **THEN** the frontend SHALL still render a coherent completed timeline without requiring artificial tool steps
