## 1. 基线与契约

- [x] 1.1 在多知识库修改前，修复当前被中断的产品选型提示测试并恢复绿色基线，记录后端与前端聚焦验证命令。
- [x] 1.2 新增 workspace、knowledge base、索引策略、Provider 引用、聚合状态和 `KnowledgeBaseScope` 领域模型及序列化测试。
- [x] 1.3 新增 workspace/KB 生命周期、范围化证据查询和有效 KB 配置的 repository/service/provider 协议，避免路由绑定 SQLite 或 Milvus 细节。
- [x] 1.4 在 `.env.example`、运行时配置和配置测试中加入稳定的默认 workspace/KB ID 与名称。

## 2. 最终 Schema 与 Clean Rebuild

- [x] 2.1 定义唯一的最终 schema 版本，从空 SQLite 直接创建 workspace、knowledge_base、document、document_chunk、parse/KG/evaluation 状态和 enrichment 字段，不使用 `ALTER`/回填过渡路径。
- [x] 2.2 使用非空列、复合唯一键、复合外键和触发器强制 workspace/KB/document/chunk 同域归属，并为 scope、状态、更新时间和文档聚合建立索引。
- [x] 2.3 删除或停用历史数据回填、可空归属、旧 schema 自动升级和兼容 migration 代码；正常启动发现旧版本时只返回 `reset_required`。
- [x] 2.4 实现 `KnowledgeStorageResetProvider`/coordinator，统一编排 SQLite、Milvus、Neo4j、报告/状态和受管理源文件的 dry-run、reset 与 initialize。
- [x] 2.5 实现仅限 CLI 的 clean-rebuild 命令，要求服务无活动写入、完整确认短语和可选备份路径；正常 HTTP API 不暴露全局清空操作。
- [x] 2.6 定义 managed-source 白名单/边界：可删除 uploads、feedback 和生成报告，但不得删除 `.env`、词表、应用配置或备份目录。
- [x] 2.7 写入 reset manifest 和 maintenance 状态，记录每个存储后端的计划、结果、错误、最终 schema 版本与完成时间；部分失败时禁止业务启动。
- [x] 2.8 clean-rebuild 后幂等创建稳定默认 workspace/Document KB、FTS5 表、Milvus collections/indexes 和 Neo4j 约束，不导入任何旧记录。
- [x] 2.9 增加 dry-run、缺少确认、活动写入、完整清空、部分失败恢复、旧 schema 拒绝、最终 DDL 约束和重复空库初始化测试。

## 3. 知识库领域服务与 API

- [x] 3.1 实现 SQLite workspace/knowledge-base repository，支持创建、列表、详情、更新、归档、可恢复状态以及 requested/effective 配置解码。
- [x] 3.2 实现知识库 service，校验仅支持 Document 类型、workspace/KB 活动状态、重复/空名称、索引开关和未生效 Provider 覆盖值。
- [x] 3.3 实现文档数、已索引 chunk 数、处理中、失败和 reset-required 聚合查询，避免 N+1 文档扫描。
- [x] 3.4 新增请求/响应 schema 和轻量 API，覆盖默认 workspace 以及知识库创建、列表、详情、更新和归档。
- [x] 3.5 增加生命周期成功、不支持类型、归档写保护、部分失败聚合和确定性默认值的 API/repository/service 测试。

## 4. 范围化文档归属与入库

- [x] 4.1 更新上传、解析、重新解析、目录上传、手动入库、启动入库、反馈入库和文档删除接口，使其要求或解析 `KnowledgeBaseScope`。
- [x] 4.2 为 document、parent/child/table/OCR chunk、解析任务、metadata 和 ingest state 写入 workspace/KB 归属，并拒绝 document/chunk 归属不一致。
- [x] 4.3 替换全局语料重置假设，实现 KB 安全重建，确保入库一个 KB 不会删除其他 KB 的向量、FTS 行、文档和入库状态。
- [x] 4.4 按 KB 约束文档列表、内容、文件预览、解析预览、删除和状态 API，同时为旧客户端保留默认 KB 行为。
- [x] 4.5 让反馈修正继承显式单一活动 KB，并为多 KB 反馈定义并测试确定性策略或校验错误。
- [x] 4.6 增加两个 KB 使用重名文件、相同 chunk 文本、部分上传失败、归档保护和 KB 局部重建的归属/入库隔离测试。
- [x] 4.7 为 document 领域模型增加 summary、keywords、suggested_questions、summary_status/error/model/generated_at/version 字段；最终 DDL 初始化由 2.1 负责。
- [x] 4.8 新增 DocumentEnrichmentProvider 接口和 OpenAI-compatible 实现，使用结构化输出生成概要、关键词和建议问题。
- [x] 4.9 在基础索引成功后触发独立 enrichment 状态机，支持关闭、失败隔离、有限重试和不重复解析的手动重试。
- [x] 4.10 实现长文档 parent chunk 分批摘要与汇总，限制 token、记录来源 chunk ID，并确保生成 metadata 绑定活动 KB。
- [x] 4.11 在最终 schema 中新增 `document_enrichment_task` 保存版本化尝试、状态、provider、错误和来源 chunk；document 只保留当前可展示结果与当前任务引用。

## 5. 范围化向量与关键词索引

- [x] 5.1 为 Milvus `rag_chunk_vectors` schema 增加 workspace/KB 字段和索引，每次 Dense/BM25 upsert 都写入来源归属。
- [x] 5.2 将 Milvus schema 能力检测统一为 `reset_required`：缺少归属字段时拒绝 Dense/BM25 查询和普通写入，只允许 clean-rebuild drop/recreate。
- [x] 5.3 在 Milvus Dense/BM25 候选召回前应用 workspace/KB filter expression，并覆盖显式单库/多库测试。
- [x] 5.4 更新 SQLite FTS5：关联权威 chunk 行，在排序和返回候选前强制知识库范围。
- [x] 5.5 更新向量/关键词删除与替换操作，使其精确作用于单个文档或 KB，不得重置其他 KB 索引。
- [x] 5.6 增加 clean-rebuild 后默认 KB 全新入库测试，并验证旧 Milvus schema 出现时系统进入 maintenance，而不是边运行边降级迁移。

## 6. 范围化检索、聊天与 Agent Workflow

- [x] 6.1 将可选请求 KB ID 解析为请求级 `KnowledgeBaseScope`；省略时只使用默认 KB；不存在或归档 ID 必须拒绝。
- [x] 6.2 为 `/rag/query`、`/chat/stream`、检索 debug 和会话 metadata 增加可选 `knowledge_base_id`/`knowledge_base_ids`，不得破坏旧请求体和 SSE framing。
- [x] 6.3 在 query understanding、Dense/BM25/FTS fan-out、RRF、reranker、父块回查、上下文、来源和推理摘要间传播 scope。
- [x] 6.4 要求父块回查和 EvidenceLookup 验证 child、parent、table 和 document 都属于活动 scope。
- [x] 6.5 更新 CitationVerifier：即使 chunk 存在，只要超出活动 KB scope，也要拒绝 citation 和图谱 source chunk，并记录安全验证 metadata。
- [x] 6.6 向 RawRAGTool、KeywordSearchTool、GraphRetrieverTool、文章读取时间线、重试和最终 Agent debug 传入同一 scope，不得扩大范围。
- [x] 6.7 增加多 KB fan-out、去重、来源归属、默认兼容、归档拒绝、跨库父块/引用阻断和 SSE 顺序不变测试。

## 7. KG、评测与横切归属

- [x] 7.1 为 KG 抽取任务、entity mention、实体向量、图节点/关系和图检索结果写入来源 workspace/KB 身份。
- [x] 7.2 在实体搜索、邻居/路径查询、图上下文和图谱 `source_chunk_id` 校验中强制 KB filter。
- [x] 7.3 为评测 case/run/result 增加可选知识库 ID，并在报告和 debug snapshot 中保存实际 scope。
- [x] 7.4 验证聊天记忆和会话文本仍与证据分离，本阶段所选 KB ID 只存为会话/请求 metadata。
- [x] 7.5 增加 KG、评测和反馈集成测试，证明证据及生成知识不能跨 KB。
- [x] 7.6 在最终 schema 中实现范围化 `query_log` 和 `answer_feedback`，记录实际 KB scope、工具、引用 chunk、结果/反馈状态，并增加跨库隔离测试。

## 8. 知识库目录前端

- [x] 8.1 新增知识库列表、创建、详情、更新、归档、聚合状态和活动 scope 的前端类型、API 方法和状态管理。
- [x] 8.2 将知识管理首页改为响应式知识库目录卡片，展示名称、描述、Document 类型、状态、文档/chunk 数和处理/失败指标。
- [x] 8.3 实现聚焦的创建 KB 对话框，支持校验、失败保留输入、刷新目录并进入新 KB。
- [x] 8.4 增加稳定 KB 详情路由/视图，在每个请求中携带活动 KB ID，并复用上传、进度、文档列表、预览、刷新和删除功能。
- [x] 8.5 增加 KB 元数据/设置编辑及受保护的归档确认，说明上传/检索影响，成功后返回目录。
- [x] 8.6 增加聊天 KB 单选/多选控件；从详情页进入聊天时预选该 KB；旧会话不得显示“全部 KB 已选择”。
- [x] 8.7 完成 loading、empty、partial failure、archived、长名称、移动端和桌面状态，不引入区块套卡片、文字重叠或第二套样式系统。
- [x] 8.8 按 WeKnora 信息架构实现知识库活动主导航、全部/收藏/最近/工作空间筛选栏、紧凑目录工具栏和响应式两列卡片网格，同时保留 Bee 品牌。
- [x] 8.9 在文档卡片/详情中显示概要生成中、已完成、失败状态，以及有界概要、关键词和建议问题入口。
- [x] 8.10 增加概要失败重试操作，重试期间不得阻塞文档预览、检索或其他知识库操作。

## 9. 验证与端到端覆盖

- [x] 9.1 运行 repository、migration、API、ingest、Milvus、FTS5、KG、Agent、citation、evaluation 和前端聚焦测试，不得通过削弱隔离断言修复回归。
- [x] 9.2 运行 `docs/DEVELOPMENT.md` 中记录的完整后端测试和前端测试/构建命令。
- [x] 9.3 完成双 KB 端到端冒烟：创建、上传重叠文档、分别/联合查询、验证引用、归档其中一个并确认另一库不受影响。
- [x] 9.4 验证未传 KB 字段的旧上传、文档列表、`/rag/query` 和 `/chat/stream` 只解析到默认 KB。
- [x] 9.5 在隔离测试环境中装入旧 SQLite/Milvus/KG/源文件夹具，执行 dry-run 与确认后的 clean-rebuild，验证旧数据归零、最终 schema 可用、manifest 完整；禁止直接编辑持久化索引文件。
- [x] 9.6 使用 Playwright 截取目录、详情和聊天 scope 的桌面/移动截图，验证控件、数量、长文本和上传进度无重叠。
- [x] 9.7 增加 enrichment 成功、Provider 缺失、超时、无效 JSON、长文分段、跨库阻断、手动重试和原始 chunk 引用回查测试。

## 10. 文档与 Change 协调

- [x] 10.1 更新架构、后端检索、前端知识 UI、开发配置、环境变量、API 文档和 README，明确本次升级是 destructive clean-rebuild，不提供历史数据迁移。
- [x] 10.2 记录 requested/effective Provider 配置、归档语义、默认兼容 scope、reset/maintenance 行为、备份与恢复步骤和第一阶段限制。
- [x] 10.3 调整 `add-auth-tenant-kb-permissions` artifacts，使其依赖本领域，并移除重复 workspace/KB 持久化、归属初始化和管理 UI 任务。
- [x] 10.4 记录 `add-search-and-deep-read-tools`、FAQ/Wiki、数据源同步、检索 Provider 注册表和物理 purge 的后续 OpenSpec 边界。
- [x] 10.5 运行 `openspec validate add-multi-knowledge-base-domain --strict`，只有 proposal/design/spec/task 契约一致时才标记 apply-ready。
- [x] 10.6 删除迁移副本验证脚本、临时 reset 文件和旧回填测试夹具，确保仓库不携带真实知识数据备份或半完成 reset manifest。
