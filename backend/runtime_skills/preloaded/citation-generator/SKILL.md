---
name: citation-generator
description: Create concise source-grounded citations and evidence notes for answers based on retrieved knowledge-base chunks.
---

# Citation Generator

Use this skill when the user needs source-grounded output, citation cleanup, or evidence notes.

## Rules

- Cite only retrieved or deep-read evidence.
- Prefer document names and section titles in visible text.
- Do not expose internal ids unless the user is using a debugging endpoint.
- Keep citations close to the claim they support.

## Output Shape

```markdown
结论：...

依据：
- 文档《...》：...
- 文档《...》：...
```
