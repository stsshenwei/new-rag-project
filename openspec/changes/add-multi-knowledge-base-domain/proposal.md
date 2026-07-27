## Why（为什么）

当前应用仍把所有上传文档视为一个全局语料库，用户无法对知识进行分库管理、指定检索范围，也无法把系统作为真正的企业知识平台使用。在继续建设深读 Agent 工具、FAQ/Wiki 知识类型、数据源同步和知识库权限之前，必须先建立一等的多知识库领域模型。

## What Changes（变更内容）

- 新增持久化的 `workspace` 和 `knowledge_base` 领域模型，并在全新数据结构中创建稳定的默认工作空间和默认文档型知识库。
- 新增知识库创建、列表、详情、更新、归档及文档/索引聚合状态接口。
- 每个文档和文档分块必须且只能属于一个知识库。
- **BREAKING**：本 change 不迁移或回填旧 metadata、chunk、向量、FTS、KG、评测、反馈与上传文件；升级时通过显式 clean-rebuild 命令清空旧知识数据，并以最终 schema 重新初始化。
- clean-rebuild 必须要求服务停止、确认短语和删除清单预览；正常启动、普通 ingest 和 schema 检测不得隐式删除数据。
- 上传、解析、文档列表、预览、删除、入库、反馈回写、Dense 检索、BM25/FTS5 检索、父块回查、KG 元数据和评测全部按 `knowledge_base_id` 隔离。
- `/rag/query` 和 `/chat/stream` 支持选择一个或多个知识库；旧客户端未传范围时仍使用默认知识库。
- 前端新增知识库目录卡片、创建流程、详情工作区、文档数量、处理状态，并从详情页进入现有上传和文档管理功能。
- 知识库目录和详情页采用与 WeKnora 一致的信息架构与交互密度：主导航、范围筛选栏、知识库卡片网格、创建入口和范围化文档视图；保留 Bee 品牌和现有技术栈，不复制 WeKnora 商标。
- 支持在同一工作空间中持续创建多个独立知识库，并确保名称、文档、索引、状态和聊天范围互不串库。
- 文档上传并完成基础解析/索引后，生成文档概要、关键词和建议问题等 enrichment 元数据，展示独立生成状态；生成失败不得影响原始文档可检索性。
- 新增知识库级索引策略和模型/存储 Provider 引用契约，但本 change 不实现多向量数据库注册表。
- 第一阶段仅支持 Document 知识库；FAQ、Wiki、外部数据源同步、共享、成员角色和完整 RBAC 不在本 change 范围内。
- 调整待实施的 `add-auth-tenant-kb-permissions` 范围：它应复用本 change 的知识库领域，只负责认证和授权，不能重复创建知识库表或初始化流程。

## Capabilities（能力范围）

### New Capabilities（新增能力）

- `knowledge-base-domain`：工作空间、Document 知识库生命周期、配置、聚合状态和兼容默认值。
- `knowledge-base-content-ownership`：文档、分块、反馈知识、KG 元数据的强制知识库归属，以及旧数据清空后按最终 schema 初始化的契约。
- `knowledge-base-scoped-retrieval`：Raw RAG、关键词检索、Agent 工具、聊天、查询和评测的单知识库/多知识库范围选择。
- `knowledge-base-management-ui`：知识库目录卡片、创建与设置流程、详情工作区和范围化文档管理。
- `document-post-processing`：上传后文档概要、关键词、建议问题及独立 enrichment 状态和失败降级。

### Modified Capabilities（修改能力）

当前尚无主规格需要修改，本 change 建立第一版契约。

## Impact（影响范围）

- **BREAKING**：旧 SQLite metadata、Milvus collection、FTS/KG/evaluation 状态、反馈知识和上传源文件不做兼容迁移；部署者必须先备份（如需要），再执行显式 clean-rebuild。
- clean-rebuild 完成后一次性创建最终 SQLite schema、FTS5 索引、Milvus collection 和默认 workspace/KB；不保留中间兼容列或旧 collection schema。
- 后端 API 和请求模型增加可选知识库范围，同时为旧客户端保留默认知识库兼容行为。
- `RAGService`、向量/关键词 Provider、Agent 工具、反馈入库、文档接口和评测流程必须全链路传播知识库身份。
- Next.js 知识管理界面从全局文档列表升级为知识库目录和范围化详情工作区。
- 文档 schema、LLM Provider 调用、处理状态和文档卡片增加概要/关键词/建议问题信息；该后处理必须具备独立失败状态和可重试边界。
- 待实施的权限 change 与本领域存在重叠，应用前必须移除其中重复的知识库持久化和初始化任务。
- 不新增外部服务；第一阶段继续使用 SQLite 和现有 Milvus。
