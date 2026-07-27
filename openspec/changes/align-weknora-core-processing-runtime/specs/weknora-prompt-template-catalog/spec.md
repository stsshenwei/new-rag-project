## ADDED Requirements

### Requirement: Complete Prompt Template Catalog
The system SHALL provide adapted YAML prompt templates for system prompts, context rendering, query rewrite, intent detection, keyword extraction, summary generation, generated questions, session title generation, graph extraction, and fallback responses.

#### Scenario: Prompt catalog loads at startup
- **WHEN** the backend starts with the default prompt template path
- **THEN** the prompt catalog validates all required template ids and placeholder declarations

### Requirement: Prompt Rendering For User Questions And Context
The system SHALL compose user questions, selected knowledge scopes, retrieved context, conversation history, and mode instructions through validated prompt templates rather than scattered hardcoded prompt strings.

#### Scenario: Quick answer renders context prompt
- **WHEN** quick answer mode generates a response from retrieved chunks
- **THEN** the final model messages use the configured context template with the user question and bounded evidence context

#### Scenario: Reasoning mode renders agent prompt
- **WHEN** intelligent reasoning mode starts an agent run
- **THEN** the system renders the selected agent system template with available tools, selected knowledge bases, language, and skill metadata

### Requirement: Prompt Template Safety
The system SHALL reject missing required placeholders, unknown template ids, malformed YAML, and unsafe prompt rendering that would expose secrets.

#### Scenario: Invalid prompt template is configured
- **WHEN** a configured prompt template is missing required content
- **THEN** the backend reports a startup/configuration error or falls back to a safe default according to configuration

### Requirement: UTF-8 Prompt Integrity
The system SHALL validate prompt templates and prompt-bearing source files as UTF-8 so Chinese prompt content and labels do not silently degrade.

#### Scenario: Mojibake-like content is detected
- **WHEN** prompt validation detects invalid encoding or known mojibake markers in required templates
- **THEN** validation fails with a file path and template id that identify the issue

