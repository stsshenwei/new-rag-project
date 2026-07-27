## 1. 依赖与认证模型

- [ ] 1.1 声明依赖已完成的 `add-multi-knowledge-base-domain`，复用其最终 workspace/knowledge_base schema、`KnowledgeBaseScope`、clean-rebuild 初始化、管理 API 与 UI。
- [ ] 1.2 新增 User、Tenant、Team、TenantMember、KnowledgeBaseMember、ApiToken 和 PermissionScope；不得重复定义 KnowledgeBase 实体。
- [ ] 1.3 新增 AuthProvider、ApiTokenProvider、PermissionProvider 和 PermissionScopeResolver 协议。
- [ ] 1.4 实现独立 SQLite auth repository、幂等 auth-schema 初始化、Token 哈希/撤销及兼容默认 principal/tenant；不得迁移或回填知识数据。

## 2. PermissionScope 与现有知识库范围求交

- [ ] 2.1 将 principal 可访问 KB 集合与请求 `KnowledgeBaseScope` 求交，空交集必须拒绝。
- [ ] 2.2 为上传、解析、列表、预览、删除、反馈和入库动作校验 viewer/editor/owner 权限，不修改现有归属 schema。
- [ ] 2.3 将交集后的同一 scope 传入 Raw RAG、FTS5、Milvus、GraphRetriever、Agent、CitationVerifier 和评测。
- [ ] 2.4 验证权限过滤不会扩大默认 KB、显式单库或显式多库范围。

## 3. FastAPI 认证边界

- [ ] 3.1 解析 Bearer Token 并通过依赖注入生成 PermissionScope；`/health` 保持公开。
- [ ] 3.2 保护文档、查询、聊天、记忆、反馈和评测端点，分别返回 401 与 403。
- [ ] 3.3 新增当前 principal、tenant/member、KB member 和 Token 创建/撤销管理 API；复用现有知识库创建/列表 API。
- [ ] 3.4 `AUTH_ENABLED=false` 时映射到现有默认 workspace/KB，不创建第二套默认 KB ID。

## 4. Agent 与审计安全

- [ ] 4.1 将 FSM `CheckPermissionScope` 从 KB 存在性校验升级为真实 principal 权限交集校验。
- [ ] 4.2 工具调用、重试、文章读取、debug 和 citation 校验保持同一权限范围。
- [ ] 4.3 日志、trace、错误和评测快照不得暴露原始 Bearer Token。

## 5. 测试

- [ ] 5.1 覆盖 Token 创建、哈希、校验、撤销及无认证兼容模式。
- [ ] 5.2 覆盖 tenant/KB membership、角色动作和单库/多库权限交集。
- [ ] 5.3 覆盖文档 API、FTS5、Milvus、GraphRetriever、Agent 和 CitationVerifier 的越权阻断。
- [ ] 5.4 验证本 change 未创建重复 workspace/knowledge_base 表、document/chunk/vector 归属列、知识数据初始化、clean-rebuild 流程和管理 UI。

## 6. 文档与验证

- [ ] 6.1 更新认证环境变量、架构、API 和检索权限流文档。
- [ ] 6.2 运行完整后端测试和 `openspec validate add-auth-tenant-kb-permissions --strict`。
