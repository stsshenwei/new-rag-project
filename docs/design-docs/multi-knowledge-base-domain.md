# 多知识库领域设计

## 领域边界

- `workspace`：后续租户与权限的稳定容器。
- `knowledge_base`：Document 知识库生命周期、索引策略、Provider 引用与聚合状态。
- `KnowledgeBaseScope`：请求级不可变范围，不存入全局服务状态。
- `document` / `document_chunk`：SQLite 权威内容，每行强制 workspace/KB 归属。

## 兼容与隔离

旧请求落到配置的默认 KB，绝不解释为全库。显式 KB 不存在或已归档时拒绝。文档、FTS、Milvus、KG、Agent、评测和引用验证共同使用同一 scope；跨库 child/parent、图谱边或 citation 即使 ID 存在也会被拒绝。

## 生命周期

第一阶段支持创建、列表、详情、更新、归档和恢复。归档是逻辑删除：禁止上传与检索，保留 SQLite、Milvus、Neo4j 和源文件，物理 purge 留给后续审计型 change。

## Provider 配置

知识库同时保存 requested 与 effective Provider。requested 是用户提交的 parser、embedding、reranker、vector store 和 enrichment 引用；effective 是当前运行时工厂实际启用值。当前工厂不支持的覆盖值保留在 requested，并把字段名记录为 `inactive_overrides`，不得静默宣称已生效。第一阶段不实现多向量数据库注册表，也不为每个 KB 创建独立 collection。

## 文档后处理

基础解析/分块/索引完成后，可异步生成概要、关键词和建议问题。长文使用 parent chunk 分批与汇总；失败可重试且不重复解析文档。生成 metadata 不能作为最终事实答案的唯一来源，必须回查原始 chunk。

## 最终 schema 与重建

本领域不迁移旧知识数据。空数据库直接创建最终 `workspace`、`knowledge_base`、document/chunk、任务、KG、审计和反馈表；非空旧 schema 只返回 `reset_required`。缺少 scope 字段的 Milvus collection 同样拒绝查询和普通写入。

clean-rebuild 默认 dry-run，执行时要求服务停止和完整确认短语 `RESET_ALL_KNOWLEDGE_DATA`。协调器先写 maintenance/manifest，再依次 reset 与 initialize SQLite、Milvus、可选 Neo4j 和受管理文件。全部成功才移除 maintenance；部分失败禁止业务启动。

`--backup-dir` 可备份 SQLite 与受管理文件，但 Milvus/Neo4j 必须使用原生备份。恢复意味着恢复一套完整的 clean-rebuild 前快照和对应应用版本，不允许把旧库手工接入最终 schema。

## 第一阶段限制

- 只支持 Document 知识库和单一默认 workspace。
- 归档不是物理删除，也不回收索引或源文件。
- 未实现用户、成员、共享、角色与 RBAC。
- 未实现 FAQ/Wiki、外部数据源同步和 Provider 实例注册表。
- 未实现旧数据导入器；重建后需要重新上传可信源文档。

## 后续边界

- `add-auth-tenant-kb-permissions`：只实现 principal、tenant、membership、role、Token 和权限范围交集。
- `add-search-and-deep-read-tools`：增加迭代搜索、文章读取和工具注册，不改变 KB 归属。
- FAQ/Wiki：新增知识类型与编辑流程。
- 数据源同步：新增连接器、游标和增量任务。
- Provider 注册表：管理多 parser/embedding/vector/reranker 实例。
- 物理 purge：需要审计、异步任务、失败恢复和派生索引清理。
