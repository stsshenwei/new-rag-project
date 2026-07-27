---
name: document-analyzer
description: Analyze document structure, key information, document type, and content quality when the user asks for document analysis.
---

# Document Analyzer

Use this skill when the user asks to analyze a document, identify its structure, extract key information, judge document type, or assess content quality.

## Method

1. Identify the document name, type, source, and available chunk count.
2. Deep-read relevant chunks before making claims.
3. Summarize structure, core topic, important facts, and gaps.
4. Separate facts supported by evidence from interpretation.

## Output

Use concise Chinese by default:

```markdown
## 文档分析

### 基本信息
- 文档：
- 类型：
- 可用证据：

### 结构
1. ...

### 关键信息
- ...

### 结论
...
```
