## ADDED Requirements

### Requirement: Quick answers use source-grounded Markdown synthesis

The system SHALL synthesize quick-mode answers with clear, source-grounded Markdown structure by default, while applying stricter tables and sections when the question and retrieved evidence call for comparison, compatibility, support, or technical-parameter presentation.

#### Scenario: Compatibility answer includes supported sections

- **WHEN** a quick-mode question asks which products, series, ONUs, switches, cables, ports, authentication methods, rates, or adapters are supported or compatible
- **AND** retrieved evidence contains matching compatibility or parameter information
- **THEN** the answer starts with a direct conclusion
- **AND** the answer uses Markdown headings, bullet lists, or tables to separate fully supported items, partially supported items, and technical parameters when those categories are present in the evidence

#### Scenario: Partial compatibility is not collapsed into full compatibility

- **WHEN** retrieved evidence distinguishes complete compatibility from partial model support
- **THEN** the answer presents partial support separately from full support
- **AND** each partial item includes the limitation or "仅部分型号支持" style note when the evidence supports it

#### Scenario: Technical parameters remain evidence-bound

- **WHEN** retrieved evidence includes technical parameters such as transmission rate, transmission distance, voltage, temperature, storage temperature, or humidity
- **THEN** the answer may include a dedicated parameter section
- **AND** each parameter value MUST be grounded in the retrieved context

### Requirement: Quick answers must not fabricate unsupported details

The system SHALL fail closed for unsupported compatibility, product, and parameter details.

#### Scenario: Missing parameter evidence

- **WHEN** the question asks for a technical parameter that is not present in the retrieved evidence
- **THEN** the answer states that the provided documents cannot determine that parameter
- **AND** the answer MUST NOT invent values, URLs, firmware versions, command flags, product attributes, or model limitations

#### Scenario: Product attributes must come from matching evidence

- **WHEN** the answer lists product models, series, port counts, supported cables, authentication methods, or access rates
- **THEN** each listed attribute MUST be supported by evidence from the same product or source context
- **AND** the answer MUST NOT merge unrelated attributes from different documents into one product claim

### Requirement: Default quick-answer behavior remains concise and structured

The system SHALL apply a lightweight Markdown structure to all quick answers and reserve special compatibility or parameter tables for question types and evidence that justify them.

#### Scenario: Non-compatibility factual question

- **WHEN** a quick-mode question is a simple factual lookup and does not ask for compatibility, support, comparison, procedure, selection, or technical parameters
- **THEN** the answer remains concise but still uses readable Markdown structure
- **AND** the system MUST NOT force irrelevant compatibility tables or parameter sections
