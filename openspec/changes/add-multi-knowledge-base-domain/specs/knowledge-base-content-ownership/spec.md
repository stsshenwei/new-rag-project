## ADDED Requirements

### Requirement: 强制文档归属
每个文档和文档 chunk SHALL 包含非空工作空间 ID 和知识库 ID，每个 chunk SHALL 继承其文档的归属。

#### Scenario: 上传到指定知识库
- **WHEN** 文档被上传或解析到指定知识库
- **THEN** 文档、parent/child/table/OCR chunk、解析任务和生成元数据 SHALL 使用相同工作空间和知识库身份

#### Scenario: 拒绝 chunk 跨库归属
- **WHEN** 写入操作试图把 chunk 归属到不同于其文档的知识库
- **THEN** repository SHALL 拒绝写入，并且 SHALL NOT 创建不一致 chunk

### Requirement: 破坏性清空与最终结构初始化
系统 SHALL 通过显式运维命令清空旧知识数据，并从空存储创建最终多知识库结构；系统 SHALL NOT 回填或兼容旧 document、chunk、向量、FTS、KG、评测、反馈和受管理源文件记录。

#### Scenario: 预览清空范围
- **WHEN** 运维人员以 dry-run 模式执行 clean-rebuild
- **THEN** 命令 SHALL 列出将删除的 SQLite 数据库、Milvus collections、Neo4j 项目数据、报告/状态文件和受管理源文件，且 SHALL NOT 修改任何数据

#### Scenario: 未确认时拒绝清空
- **WHEN** 服务仍有活动写入或调用者未提供完整确认短语
- **THEN** clean-rebuild SHALL 拒绝执行，并且 SHALL NOT 部分删除数据

#### Scenario: 执行全量清空重建
- **WHEN** 服务已停止且调用者提供完整确认短语执行 clean-rebuild
- **THEN** 系统 SHALL 清空约定的旧知识数据、创建最终 SQLite/FTS5/Milvus/Neo4j 结构、创建默认 workspace/KB，并记录 reset manifest

#### Scenario: 发现旧 schema
- **WHEN** 正常启动检测到旧 schema 或不兼容 collection
- **THEN** 系统 SHALL 进入 `reset_required`/maintenance 状态并拒绝业务写入，且 SHALL NOT 自动删除、自动回填或混合运行新旧结构

#### Scenario: 清空部分失败
- **WHEN** 任一存储后端在清空或最终结构初始化期间失败
- **THEN** reset manifest SHALL 记录失败阶段，系统 SHALL 保持 maintenance 状态，且 SHALL NOT 宣告初始化完成

### Requirement: 派生索引归属
每个关键词、向量、实体和图谱证据行 SHALL 携带其来源 chunk 的知识库身份。

#### Scenario: 索引 child chunk
- **WHEN** child、table 或 OCR chunk 被索引
- **THEN** Milvus Dense/BM25 行和 FTS5 权威查询 SHALL 可追溯到同一工作空间和知识库

#### Scenario: 写入 KG 证据
- **WHEN** KG 抽取创建 entity mention 或证据绑定关系
- **THEN** 任务、mention、实体向量 metadata 和关系证据 SHALL 包含来源知识库 ID

### Requirement: 反馈知识归属
反馈生成的知识 SHALL 写入明确知识库，禁止无归属进入全局语料。

#### Scenario: 单库聊天提交修正
- **WHEN** 用户在一个活动知识库范围内提交答案修正
- **THEN** 生成的反馈文档和全部派生 chunk SHALL 继承该知识库 ID

#### Scenario: 多库反馈范围不明确
- **WHEN** 多知识库答案提交反馈但没有明确目标知识库
- **THEN** 系统 SHALL 要求指定目标，或使用有文档记录的确定性策略，并在反馈 metadata 中记录该策略

### Requirement: 查询与反馈审计归属
query log 和 answer feedback SHALL 保存请求的工作空间、知识库范围、来源文档/chunk 以及生成记录，且 SHALL NOT 以无范围全局记录替代证据所有权。

#### Scenario: 记录范围化查询
- **WHEN** 单库或多库查询完成
- **THEN** query log SHALL 保存请求选择的知识库 ID、实际工具范围、引用 chunk 和结果状态

#### Scenario: 保存答案反馈
- **WHEN** 用户评价或修正已生成答案
- **THEN** answer feedback SHALL 关联 query/answer、目标知识库和来源 chunk；需要生成反馈文档时 SHALL 继承同一目标知识库

### Requirement: 归档库写保护
归档知识库 SHALL 保留现有归属记录，但 SHALL 拒绝内容变更。

#### Scenario: 向归档库上传
- **WHEN** 客户端尝试向归档知识库上传、重新解析、反馈回写或入库
- **THEN** 系统 SHALL 拒绝操作且不得修改现有内容
