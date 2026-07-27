## ADDED Requirements

### Requirement: How-to answer structure
The backend SHALL guide how-to answers to use structured, source-grounded Markdown.

#### Scenario: How-to question with enough evidence
- **WHEN** the user asks a how-to/procedure question and retrieved context is sufficient
- **THEN** the answer SHALL use Markdown sections such as prerequisites, steps, commands, notes, or cautions when supported by evidence

#### Scenario: Commands in evidence
- **WHEN** the retrieved context contains shell commands, config snippets, or install commands
- **THEN** the answer SHALL render them in fenced code blocks with an appropriate language hint when possible

#### Scenario: Missing evidence
- **WHEN** the retrieved context does not contain enough information for a requested step or parameter
- **THEN** the answer SHALL explicitly state that the information cannot be determined from the provided documents

#### Scenario: No unsupported prior knowledge
- **WHEN** generating a how-to answer
- **THEN** the answer MUST NOT invent install flags, commands, versions, URLs, or prerequisites that are not supported by retrieved context

#### Scenario: Professional how-to sections
- **WHEN** the user asks for setup, installation, deployment, repair, or operation steps
- **THEN** the answer SHOULD use clear Markdown sections such as `前提条件`, `安装步骤`, `验证`, and `注意事项` when supported by evidence

#### Scenario: Insufficient how-to evidence
- **WHEN** the retrieved documents only support part of the requested procedure
- **THEN** the answer SHALL provide only the supported steps and explicitly state which requested parts cannot be determined from the provided documents

### Requirement: Code block rendering
The frontend SHALL render Markdown code blocks with a language label and copy-code control.

#### Scenario: Fenced command block
- **WHEN** an assistant answer contains a fenced code block
- **THEN** the UI SHALL show the code in a styled block with a language label such as `Bash` when a language is present

#### Scenario: Copy code
- **WHEN** the user clicks the copy-code control on a code block
- **THEN** the UI SHALL copy that code block's text to the clipboard when browser support is available

#### Scenario: Clipboard unavailable
- **WHEN** clipboard access is unavailable or copy fails
- **THEN** the code block SHALL remain readable and selectable without breaking the answer UI

#### Scenario: Inline code remains compact
- **WHEN** the answer contains inline code
- **THEN** inline code SHALL continue rendering inline rather than using block controls
