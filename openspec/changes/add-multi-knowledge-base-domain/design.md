## Context（背景）

后端已经具备结构化解析、parent-child chunk、SQLite 元数据/FTS5、Milvus Dense/BM25、KG 元数据、Agent 工具和评测能力，但所有数据仍属于一个全局语料库。前端知识管理区也只是全局文档列表。借鉴 WeKnora 的重点不是卡片样式，而是由入库、检索、模型、权限、Agent 工具和界面共同遵守的稳定知识库边界。

本 change 先引入领域边界，不与认证耦合。待实施的 `add-auth-tenant-kb-permissions` 当前包含重复的知识库持久化设计，后续必须调整为复用这里的领域模型。

约束：

- 本次允许放弃全部旧知识数据，不承担原地升级和历史数据兼容成本。
- 旧客户端不传知识库范围时，通过确定性的默认知识库保持兼容。
- SQLite 继续作为业务数据事实源，Milvus 是可重建的派生索引。
- 第一种知识库类型仅为 `document`，FAQ、Wiki 和同步数据源由后续 change 增加。
- Provider 引用只建立配置契约，本 change 不建设多向量库工厂。

## Goals / Non-Goals（目标与非目标）

**目标：**

- 建立工作空间和知识库实体、生命周期、配置和聚合状态。
- 文档、分块、向量、关键词、KG、反馈、查询、聊天、Agent 和评测全部携带知识库身份。
- 支持单库/多库检索，同时提供确定性的旧客户端兼容默认值。
- 前端提供知识库目录和范围化详情工作区。
- 在不阻塞基础入库的前提下，为上传文档生成概要、关键词和建议问题元数据。
- 提供受保护的破坏性 clean-rebuild，并一次性建立最终 schema 和派生索引。

**非目标：**

- 登录、用户、成员、角色、共享、邀请、API Token 和授权策略。
- FAQ/Wiki 知识库和外部数据源同步。
- 每个知识库独立 Milvus collection 或多个向量数据库实现。
- 日常单知识库物理 purge；本 change 只提供部署期的全局 clean-rebuild。
- 直接复制 WeKnora 的 Go/Vue 实现或复刻全部设置。

## Decisions（关键决策）

### 1. 在知识库上方保留轻量工作空间

持久化：

```text
workspace(id, name, description, status, created_at, updated_at)
knowledge_base(id, workspace_id, name, description, type, status,
               indexing_strategy_json, provider_config_json,
               created_at, updated_at)
```

理由：工作空间为后续租户/权限提供稳定容器，同时不把身份系统塞进本 change。初始部署只创建一个默认工作空间。

未采用“知识库直接作为顶层实体”，因为未来加租户时会再经历一次所有权迁移。

### 2. 共享 SQLite schema 和 Milvus collection，以字段实现逻辑隔离

最终 schema 从空库直接创建。`document`、`document_chunk` 从第一行数据起就要求非空 `workspace_id` 和 `knowledge_base_id`，并使用复合唯一键/外键约束 workspace、KB、document 与 chunk 的同域关系，不保留先可空再回填的过渡结构。Milvus `rag_chunk_vectors` 同样从创建时包含这两个字段和标量索引，Dense/BM25 查询必须带过滤表达式。FTS5 使用权威 chunk 行执行知识库约束。

理由：共享存储运维成本低，也支持跨知识库 fan-out。第一阶段不采用每库一个数据库/collection，避免 collection 生命周期、schema 漂移和跨库查询复杂化。

最终物理边界：

```text
rag_metadata.sqlite3
  workspace
  knowledge_base
  document
  document_chunk
  parse_task
  document_enrichment_task
  kg_extraction_task
  entity_mention
  graph_community_summary
  query_log
  answer_feedback
  document_chunk_fts (FTS5 派生索引)

rag_eval.sqlite3
  eval_run / eval_result（case snapshot 随 result 固化）

rag_memory.sqlite3
  conversation / message / memory（不作为知识证据）

Milvus
  rag_chunk_vectors
  kg_entity_vectors

Neo4j
  scoped entity/document/chunk nodes and evidenced relations
```

`knowledge_base` 使用 `(workspace_id, id)` 唯一约束；`document` 使用 `(workspace_id, knowledge_base_id, id)` 唯一约束；`document_chunk` 以同一复合键引用 document。解析、enrichment、KG mention、query/feedback 行使用同样的 scope 键。JSON 只保存可演进配置、metadata 和模型输出列表，不保存本可由外键表达的所有权。

### 3. 使用请求级 `KnowledgeBaseScope`

新增值对象：

```text
KnowledgeBaseScope
  workspace_id
  selected_knowledge_base_ids
  optional_document_ids
  compatibility_default
```

HTTP 层只解析一次，然后传入 `RAGService`、检索 Provider、Agent 工具、GraphRetriever 和评测。禁止把当前 KB 放入全局可变服务状态，以免并发请求串库。

### 4. 旧客户端落到默认库，绝不解释为“所有知识库”

clean-rebuild 后首次启动使用稳定配置 ID 创建默认工作空间和默认 Document KB。不会读取或回填旧记录。请求未传 KB 时解析为默认 KB，并记录 `compatibility_default=true`。

这既保持当前行为，也避免系统进入多库后产生默认全库检索和潜在数据泄漏。

### 5. 索引策略和 Provider 引用属于知识库配置

每个 KB 保存 Dense、keyword、graph 等索引开关，以及 embedding、reranker、vector store、parser 默认引用。运行时仍可使用全局 Provider；当前工厂无法激活的覆盖配置必须显示为“已请求但未生效”，不能静默套用。

### 6. 生命周期第一阶段采用归档，不做物理删除

删除 API 将状态改为 `archived`。归档库不出现在默认列表中，不能上传和检索，但 SQLite、Milvus、图谱及源文件暂时保留。物理 purge 由后续具备审计和失败恢复能力的任务流程实现。

### 7. 前端以目录和详情工作区组织

知识管理首页展示 KB 卡片；详情工作区由 KB ID 标识。卡片显示名称、描述、类型、状态、文档数、已索引 chunk 数、处理中和失败数。上传、文档列表、预览继续复用现有能力，但请求必须携带活动 KB ID。

### 8. 与权限 change 明确所有权

本 change 负责 workspace/KB 表、文档与 chunk 归属、范围传播、clean-rebuild 初始化和管理 UI。`add-auth-tenant-kb-permissions` 后续只负责 principal、membership、role、授权和 scope 交集，必须删除重复任务。

### 9. 借鉴 WeKnora 的知识库页面信息架构，而不是只复制配色

知识管理区域采用三层结构：

```text
Bee 主导航
  └─ 知识库
       ├─ 范围筛选：全部 / 收藏 / 最近 / 当前工作空间
       ├─ 目录工具栏：标题、数量、创建知识库
       └─ 知识库卡片网格
            └─ 详情：概要、文档、处理状态、设置、开始聊天
```

卡片保持紧凑、低圆角和可扫描信息密度，显示名称、描述、类型、文档数、处理中/失败数和创建者占位信息。视觉上参考 WeKnora 的浅色导航、绿色状态语义和两列目录，但继续使用 Bee 名称、现有图标库和 CSS 变量，不复制 Logo、品牌文案或源码组件。

### 10. 文档概要作为独立后处理状态机

基础路径先完成：

```text
uploaded → parsing → parsed → chunked → indexed
```

随后触发独立 enrichment：

```text
summary_status: none → pending → processing → completed
                                      └→ failed（可重试）
```

文档保存 `summary`、`keywords_json`、`suggested_questions_json`、`summary_status`、`summary_error`、`summary_model_ref`、`summary_generated_at` 和 `summary_version`。输入优先使用 parent chunks 的有界合并内容；长文档采用分段摘要再汇总，禁止把完整超长文档一次性塞入模型。

概要、关键词和建议问题必须绑定原文档及知识库，只作为导航、推荐问题和可选检索增强 metadata，不替代原始 chunk 证据。Provider 未配置或生成失败时，文档仍保持 `indexed` 且可查询，UI 显示概要待生成/失败状态并允许重试。

### 11. 使用显式 clean-rebuild 代替兼容迁移

不再维护旧 schema 到新 schema 的字段回填逻辑。提供仅限运维使用的 CLI，例如：

```text
python -m app.scripts.rebuild_knowledge_storage \
  --confirm RESET_ALL_KNOWLEDGE_DATA \
  --delete-managed-sources
```

命令必须先执行预检并输出删除清单，拒绝在可探测到应用写入进程时运行。确认后按下列边界清空：

- SQLite metadata、KG metadata、evaluation 数据库及其 WAL/SHM，随后以最终 DDL 重建；
- Milvus `rag_chunk_vectors` 与 `kg_entity_vectors` collection，随后按最终字段和索引重建；
- 配置的 Neo4j 数据库中带本项目作用域标识的知识节点与关系；
- FTS5、evaluation report、ingest state、生成的 feedback 知识；
- 与旧知识证据绑定的 conversation/message scope、query log 和 memory；用户身份、认证密钥与应用配置不属于清空范围；
- `--delete-managed-sources` 启用时，删除受管理的 uploads/feedback 源文件，但保留 `.env`、词表和应用配置白名单。

正常应用启动只做 schema 版本检查。发现旧 schema 时进入 `reset_required` 并拒绝 ingest/查询写入，不得自动删除、自动回填或边运行边升级。clean-rebuild 写入 manifest，记录时间、目标、schema 版本和各存储结果；任一存储失败时保持 maintenance 状态，禁止以混合新旧结构启动。

未采用“启动时自动清库”，因为误用环境变量或启动命令就造成不可恢复删除的风险过高。未采用“继续保留迁移代码”，因为用户已明确放弃旧数据，过渡列、回填触发器和双路径测试会长期增加复杂度。

## Risks / Trade-offs（风险与权衡）

- **误删仍有价值的旧数据**：clean-rebuild 必须停服务、展示删除清单、要求完整确认短语，并支持先生成备份；正常启动永不自动清空。
- **多存储清空部分成功**：使用 reset manifest 和 maintenance 状态记录每个后端结果；全部最终 schema 就绪前拒绝启动业务写入。
- **现有 Milvus schema 没有范围字段**：启动只标记 `reset_required` 并拒绝向量写入/查询；由 clean-rebuild drop/recreate collection，不再尝试兼容旧行。
- **Provider 遗漏范围过滤**：为 Dense、BM25、FTS5、父块回查、GraphRetriever、Agent 工具分别增加契约测试；空 scope 在 Provider 边界直接拒绝。
- **归档内容继续占空间**：第一阶段接受保留，明确显示归档状态，后续单独设计 purge。
- **全局 Provider 与 KB 覆盖配置冲突**：分别展示 requested/effective 配置，只有当前工厂支持时才激活覆盖值。
- **权限 change 重复实现**：在应用权限 change 前先修改其 proposal/design/tasks，使其依赖本 change。
- **前端页面继续膨胀**：目录、卡片、创建对话框、设置和详情拆为聚焦组件，继续使用现有数据层和样式系统。
- **概要生成增加 LLM 成本和延迟**：使用独立状态、长度上限、批处理/重试边界和知识库级开关；基础索引完成后即可检索。
- **模型生成的概要失真**：概要仅作导航 metadata，答案引用仍必须回到原始 document_chunk；保存生成模型和版本以便重建。

## Clean Rebuild Plan（清空重建计划）

1. 停止 API、后台 ingest、KG extraction 和 enrichment worker；检查没有活动写入。
2. 可选生成 SQLite、Milvus/Neo4j 导出和受管理源文件备份，并验证备份路径不位于待删除目录。
3. 以 dry-run 运行 clean-rebuild，审阅 SQLite、Milvus、Neo4j、报告、状态和源文件删除清单。
4. 输入完整确认短语执行 reset；写入 manifest 并进入 maintenance 状态。
5. 清空旧知识数据，按最终 DDL 创建 SQLite 表/约束/FTS5、Milvus collections/indexes 和 Neo4j 约束。
6. 创建稳定的默认 workspace/Document KB，执行 schema/invariant 自检；不得回填任何旧记录。
7. 启动新代码，验证空知识库目录、旧客户端默认 scope 和新 KB 创建流程。
8. 重新上传或从受信任备份显式导入源文档，再走正常 ingest/enrichment；导入不是 migration 的隐式步骤。
9. 通过双 KB 检索、引用、Agent、KG 和评测隔离验收后退出 maintenance。
10. 回滚只允许回滚到 clean-rebuild 前的完整备份；不得把旧应用指向新 schema，也不得手工编辑持久化索引文件。

## Open Questions（待确认问题）

- 反馈修正默认继承活动 KB，还是进入专用反馈 KB？当前建议继承活动 KB。
- 会话是否立即持久化选中的 KB ID？当前建议在可用时写入会话/消息 metadata。
- 第一版 UI 是否提供恢复归档 KB？后端状态模型保留恢复能力，初始 UI 可以暂不展示。
