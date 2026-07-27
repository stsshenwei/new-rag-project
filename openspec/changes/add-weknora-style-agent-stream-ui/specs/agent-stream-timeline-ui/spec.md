## ADDED Requirements

### Requirement: Agent timeline panel
The chat UI SHALL render a WeKnora-style timeline panel for assistant messages with normalized agent stream events.

#### Scenario: Timeline appears for agentic chat
- **WHEN** an assistant message has normalized agent stream events
- **THEN** the chat UI SHALL render a timeline panel below the assistant answer area or while the answer is streaming.

#### Scenario: Timeline hidden for non-agentic chat
- **WHEN** an assistant message has no normalized agent stream events
- **THEN** the chat UI SHALL NOT show an empty timeline panel.

#### Scenario: Existing reasoning remains available
- **WHEN** an assistant message also has legacy reasoning data
- **THEN** the UI SHALL keep the reasoning panel available as secondary retrieval detail.

### Requirement: Timeline run header
The timeline panel SHALL display a compact run header with progress and status.

#### Scenario: Running header
- **WHEN** the agent run is active
- **THEN** the header SHALL show running status, completed step count, total known step count, and elapsed time.

#### Scenario: Completed header
- **WHEN** the agent run is complete
- **THEN** the header SHALL show completed status, completed step count, total step count, and elapsed time.

#### Scenario: Partial or failed header
- **WHEN** the agent run is partial or failed
- **THEN** the header SHALL show partial or failed status and a concise failure summary.

### Requirement: Step timeline rendering
The timeline panel SHALL render derived timeline steps with readable labels and status indicators.

#### Scenario: Stage labels are user-facing
- **WHEN** the timeline renders Agent FSM stages
- **THEN** it SHALL use user-facing labels such as "理解问题", "规划检索", "检查权限", "运行检索", "融合证据", "校验引用", and "返回答案" instead of raw internal class names.

#### Scenario: Running step is visually distinct
- **WHEN** a timeline step is running
- **THEN** the UI SHALL show a running indicator or subtle loading animation on that step.

#### Scenario: Completed step is visually distinct
- **WHEN** a timeline step is completed
- **THEN** the UI SHALL show a completed status indicator.

#### Scenario: Skipped or failed step is visually distinct
- **WHEN** a timeline step is skipped or failed
- **THEN** the UI SHALL show skipped or failed styling and a concise reason when available.

### Requirement: Tool result summaries
The timeline panel SHALL render compact summaries for retrieval tools and verification events.

#### Scenario: Raw RAG result summary
- **WHEN** Raw RAG tool observation data is available
- **THEN** the timeline SHALL show a compact summary with matched evidence count, citation count when available, and visible source chunk count.

#### Scenario: Keyword result summary
- **WHEN** Keyword Search tool observation data is available
- **THEN** the timeline SHALL show a compact summary with keyword match count and visible source chunk count.

#### Scenario: Graph result summary
- **WHEN** GraphRetriever tool observation data is available
- **THEN** the timeline SHALL show a compact summary with entity count, relation/path count when available, and source chunk count.

#### Scenario: Evidence summary
- **WHEN** evidence summary data is available
- **THEN** the timeline SHALL show fused evidence count, used chunk count, graph path count, confidence, and sufficiency status.

#### Scenario: Citation verification summary
- **WHEN** citation verification data is available
- **THEN** the timeline SHALL show whether verification passed and how many chunks were verified or rejected.

### Requirement: Collapse and expansion behavior
The timeline panel SHALL support readable streaming and completed states.

#### Scenario: Expanded while running
- **WHEN** an agent run is still streaming
- **THEN** the timeline SHALL default to expanded so the user can watch progress.

#### Scenario: Collapsible after completion
- **WHEN** an agent run completes
- **THEN** the timeline SHALL be collapsible and retain a compact header summary.

#### Scenario: User expansion is preserved during current message
- **WHEN** a user expands or collapses the timeline for a message
- **THEN** the UI SHALL preserve that state while the message remains mounted.

### Requirement: Responsive timeline layout
The timeline panel SHALL be usable on desktop and mobile viewports.

#### Scenario: Desktop timeline fits chat column
- **WHEN** the timeline renders in the desktop chat column
- **THEN** text, chips, and cards SHALL fit within the message container without horizontal overflow.

#### Scenario: Mobile timeline wraps content
- **WHEN** the timeline renders on mobile width
- **THEN** step titles, source chunk chips, and summaries SHALL wrap or truncate cleanly without overlapping other UI.

### Requirement: Timeline compatibility with answer rendering
The timeline SHALL NOT interfere with answer streaming, sources, document preview, memory notices, or feedback.

#### Scenario: Answer tokens stream normally
- **WHEN** the timeline receives agent events while answer tokens stream
- **THEN** answer content SHALL continue appending normally.

#### Scenario: Source buttons remain usable
- **WHEN** a message contains sources and a timeline
- **THEN** source buttons SHALL remain visible and clickable.

#### Scenario: Feedback remains usable
- **WHEN** a message contains a completed answer and a timeline
- **THEN** feedback controls SHALL remain visible and usable.
