## ADDED Requirements

### Requirement: 请求级知识库范围
查询、聊天、文档、Agent、图谱和评测操作 SHALL 在访问证据前解析请求级知识库范围。

#### Scenario: 显式单库查询
- **WHEN** 请求选择一个活动知识库 ID
- **THEN** 所有检索 Provider 和证据查询 SHALL 只访问该知识库

#### Scenario: 显式多库查询
- **WHEN** 请求选择多个活动知识库 ID
- **THEN** 检索 SHALL 只在所选知识库中 fan-out，按 chunk 身份去重，并保留每条结果的知识库 ID

#### Scenario: 旧请求没有范围
- **WHEN** 旧客户端未发送知识库 ID
- **THEN** 系统 SHALL 解析为默认知识库并记录兼容 metadata，且 SHALL NOT 检索全部知识库

### Requirement: Dense 与关键词范围检索
Dense、Milvus BM25 和 SQLite FTS5 检索 SHALL 在排序或融合前强制约束知识库 ID。

#### Scenario: Milvus 范围查询
- **WHEN** 为所选知识库执行 Dense 或 BM25 检索
- **THEN** Milvus filter expression SHALL 在候选召回前包含工作空间和知识库 ID

#### Scenario: SQLite FTS5 范围查询
- **WHEN** 关键词检索使用 SQLite FTS5
- **THEN** 结果 SHALL 先关联权威 chunk 行并按知识库 ID 过滤，再返回候选

#### Scenario: 向量 schema 缺少范围字段
- **WHEN** 当前 Milvus collection 无法强制知识库过滤
- **THEN** 系统 SHALL 标记 `reset_required`、拒绝无范围查询和普通写入，并要求通过 clean-rebuild drop/recreate 最终 collection

### Requirement: 范围化证据展开与引用
父块回查、文档查询、来源提取、上下文构建和引用验证 SHALL 保留并验证知识库归属。

#### Scenario: 回查父块
- **WHEN** child 命中展开为 parent 或 table 上下文
- **THEN** 父块 SHALL 与 child 属于同一文档和知识库

#### Scenario: 验证引用归属
- **WHEN** CitationVerifier 验证 citation 或图谱 `source_chunk_id`
- **THEN** 即使 chunk ID 存在，只要它不属于活动知识库范围，验证器 SHALL 拒绝该证据

### Requirement: Agent 工具范围传播
每个 Agent 检索工具 SHALL 接收相同的知识库范围，并在安全 debug metadata 中展示所选范围。

#### Scenario: Agent 执行多个工具
- **WHEN** FSM 调用 RawRAGTool、KeywordSearchTool 或 GraphRetrieverTool
- **THEN** 每个工具 SHALL 只查询所选知识库，重试或后续检索 SHALL NOT 扩大范围

### Requirement: 文档接口范围
文档列表、预览、解析、上传、重新解析和删除 SHALL 要求或解析知识库范围。

#### Scenario: 查询知识库文档
- **WHEN** 客户端打开知识库详情工作区
- **THEN** 文档 API SHALL 只返回该知识库拥有的文档

### Requirement: 评测范围
评测 case SHALL 支持选择一个或多个知识库，并随结果记录实际范围。

#### Scenario: 执行范围化评测
- **WHEN** 评测 case 声明知识库 ID
- **THEN** runner SHALL 在这些知识库中执行检索，并在 run/result debug metadata 中保存其 ID
