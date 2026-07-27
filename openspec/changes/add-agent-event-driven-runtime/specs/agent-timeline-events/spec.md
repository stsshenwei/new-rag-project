## ADDED Requirements

### Requirement: Frontend Normalizes Agent Domain Events
The frontend SHALL normalize Agent domain events into the existing timeline model or a backwards-compatible extension.

#### Scenario: Domain event received
- **WHEN** the chat stream receives an Agent domain event payload
- **THEN** the frontend SHALL create a timeline event with stable id, sequence, kind, status, summary, source chunk ids, and sanitized metadata

#### Scenario: Unknown event received
- **WHEN** the frontend receives an unrecognized additive Agent event
- **THEN** it SHALL keep rendering the answer and SHALL fall back to a generic safe timeline item or ignore the event without crashing

### Requirement: Weknora-Like Timeline Stages
The frontend SHALL display the Agent lifecycle using user-facing stages similar to Weknora.

#### Scenario: Normal sourced run
- **WHEN** a reasoning run emits query, thought, tool, result, reflection, references, final answer, and completion events
- **THEN** the timeline SHALL display a coherent process from understanding the question through retrieval, reflection, references, answer generation, and completion

#### Scenario: Remedial retrieval run
- **WHEN** a reasoning run emits `agent_remedial_search`
- **THEN** the timeline SHALL show the remedial retrieval as a distinct follow-up search caused by an evidence gap

### Requirement: Tool Pairing
The frontend SHALL pair Agent tool calls and tool results by call id.

#### Scenario: Matching result
- **WHEN** a tool result arrives with the same call id as a prior tool call
- **THEN** the frontend SHALL update the same timeline step instead of creating an unrelated duplicate tool step

#### Scenario: Missing call
- **WHEN** a tool result arrives without a known call id
- **THEN** the frontend SHALL render a safe standalone result item without crashing

### Requirement: Public Thought Presentation
The frontend SHALL present thought and reflection events as public audit summaries, not hidden reasoning.

#### Scenario: Thought event rendered
- **WHEN** the frontend renders an `agent_thought` event
- **THEN** the visible copy SHALL describe public progress or evidence organization and SHALL NOT label it as private chain-of-thought

#### Scenario: Reflection event with gap
- **WHEN** the frontend renders an `agent_reflection` event containing an evidence gap
- **THEN** the timeline SHALL show the gap and correction direction in concise user-facing language

### Requirement: Completion Summary
The frontend SHALL derive a final run summary from Agent domain events.

#### Scenario: Completed run
- **WHEN** `agent_complete` is received after final answer streaming
- **THEN** the frontend SHALL mark the timeline complete and summarize elapsed time, tool calls, referenced documents, and whether remedial retrieval was used when that metadata is available

#### Scenario: Partial or insufficient run
- **WHEN** the Agent completes with insufficient evidence
- **THEN** the frontend SHALL mark the run as partial or insufficient instead of showing a successful completion state
