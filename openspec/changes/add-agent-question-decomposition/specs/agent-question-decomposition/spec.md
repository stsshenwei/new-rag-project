## ADDED Requirements

### Requirement: Decomposition decision
The system SHALL decide whether each chat question requires agentic decomposition before running multi-step retrieval.

#### Scenario: Simple question bypasses decomposition
- **WHEN** a user asks a direct single-fact question
- **THEN** the system SHALL use the existing single-pass RAG retrieval path without generating subquestions.

#### Scenario: Complex question triggers decomposition
- **WHEN** a user asks a comparative, multi-condition, procedural, or diagnostic question
- **THEN** the system SHALL generate a structured decomposition plan before retrieval.

### Requirement: Structured subquestion plan
The system SHALL represent decomposition as a bounded structured plan.

#### Scenario: Valid plan has bounded subquestions
- **WHEN** decomposition succeeds
- **THEN** the plan SHALL include no more than the configured maximum number of subquestions.

#### Scenario: Subquestions include purpose metadata
- **WHEN** a plan contains subquestions
- **THEN** each subquestion SHALL include an ID, a question, and a purpose.

### Requirement: Per-subquestion retrieval
The system SHALL retrieve evidence for each valid subquestion using the existing RAG retrieval pipeline.

#### Scenario: Subquestion uses existing retrieval
- **WHEN** a subquestion is executed
- **THEN** the system SHALL run existing query understanding, hybrid retrieval, and parent recall for that subquestion.

#### Scenario: Subquestion failure is isolated
- **WHEN** one subquestion retrieval fails
- **THEN** the system SHALL continue with remaining subquestions and record the failed step in the agent trace.

### Requirement: Evidence aggregation
The system SHALL aggregate subquestion evidence for final answer generation.

#### Scenario: Duplicate evidence is merged
- **WHEN** multiple subquestions return the same source chunk or parent context
- **THEN** the system SHALL deduplicate the evidence while preserving which subquestions matched it.

#### Scenario: Final answer uses grouped evidence
- **WHEN** the final answer is generated after decomposition
- **THEN** the prompt SHALL include the original question, the visible plan summary, and grouped subquestion evidence.

### Requirement: Fallback behavior
The system SHALL fall back to the current single-pass RAG path when decomposition is unavailable or invalid.

#### Scenario: Planner fails
- **WHEN** the planner raises an error or returns invalid output
- **THEN** the system SHALL answer using the original single-pass RAG flow.

#### Scenario: No subquestion evidence
- **WHEN** all subquestions fail or return no usable evidence
- **THEN** the system SHALL answer using the original single-pass RAG flow.

### Requirement: Configuration controls
The system SHALL provide runtime configuration for agentic decomposition behavior.

#### Scenario: Decomposition disabled
- **WHEN** decomposition is disabled by configuration
- **THEN** the system SHALL not call the planner and SHALL use the existing single-pass RAG path.

#### Scenario: Max subquestions enforced
- **WHEN** the planner returns more subquestions than configured
- **THEN** the system SHALL keep only the allowed number of valid subquestions.
