## ADDED Requirements

### Requirement: Structured Evidence Reflection
The system SHALL evaluate retrieved and deep-read evidence through structured public reflection before final answer generation.

#### Scenario: Evidence is sufficient
- **WHEN** initial search and deep-read evidence answer the user's question
- **THEN** the backend SHALL emit an `agent_reflection` event with sufficient completion status and proceed to references and final answer generation

#### Scenario: Evidence has a gap
- **WHEN** deep-read evidence is relevant but missing a needed entity, date, parameter, compatibility detail, or other answer-critical fact
- **THEN** the backend SHALL emit an `agent_reflection` event that identifies the public evidence gap and a correction query when one can be derived

### Requirement: Bounded Remedial Retrieval
The system SHALL perform bounded remedial retrieval when reflection identifies a repairable evidence gap.

#### Scenario: Correction query exists
- **WHEN** reflection reports an evidence gap with a correction query and remedial attempts remain
- **THEN** the runtime SHALL emit `agent_remedial_search`, perform an additional knowledge-base retrieval pass, and deep-read newly selected evidence before final synthesis

#### Scenario: Attempt limit reached
- **WHEN** reflection still reports an evidence gap after the configured remedial attempt limit is reached
- **THEN** the runtime SHALL stop retrieval and produce an insufficient-evidence answer instead of continuing the loop

### Requirement: Remedial Evidence Merge
The system SHALL merge remedial evidence with initial evidence without duplicating already-read chunks.

#### Scenario: Remedial search returns duplicate chunks
- **WHEN** remedial retrieval returns chunk ids that were already searched or deep-read
- **THEN** the runtime SHALL deduplicate those chunks and SHALL NOT count them as new remedial evidence

#### Scenario: Remedial search adds useful chunks
- **WHEN** remedial retrieval returns new traceable chunks
- **THEN** the runtime SHALL add them to the evidence set, update source chunk ids, and include them in the final reference event when used

### Requirement: Remedial Retrieval Observability
The system SHALL make remedial retrieval visible and auditable.

#### Scenario: Remedial search runs
- **WHEN** a remedial retrieval pass executes
- **THEN** the backend SHALL record the triggering gap, correction query, attempt number, tool calls, result counts, and selected chunk ids in sanitized event metadata

#### Scenario: Remedial search is skipped
- **WHEN** remedial retrieval is not run because the gap is not repairable, no correction query exists, or attempts are exhausted
- **THEN** the backend SHALL emit a public reflection or completion event explaining the skip reason without exposing private reasoning

### Requirement: Quick Mode Isolation
The system SHALL keep quick-answer mode independent from the reflective remedial loop.

#### Scenario: Quick mode request
- **WHEN** `/chat/stream` runs in quick mode
- **THEN** the backend SHALL NOT invoke the open-ended Agent remedial retrieval loop
