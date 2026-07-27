# API

## 知识库生命周期

- `GET /workspaces/default`：读取稳定默认工作空间。
- `GET /knowledge-bases?workspace_id=...&include_archived=false`：列出知识库及聚合状态。
- `POST /knowledge-bases`：创建 Document 知识库；支持 `name`、`description`、`indexing_strategy` 和 `provider_config`。
- `GET /knowledge-bases/{knowledge_base_id}`：读取详情、requested/effective Provider 配置和聚合状态。
- `PATCH /knowledge-bases/{knowledge_base_id}`：更新名称、描述、索引策略或 Provider 请求值。
- `DELETE /knowledge-bases/{knowledge_base_id}`：逻辑归档。默认 KB 不可归档。
- `POST /knowledge-bases/{knowledge_base_id}/restore`：恢复归档状态。

第一阶段只支持 `type=document`。归档 KB 默认不出现在列表中，不能上传或检索，但不会物理删除内容。

## 文档范围

以下接口接受单个 `knowledge_base_id`；省略时只解析为 `DEFAULT_KNOWLEDGE_BASE_ID`，不表示全部知识库：

- `POST /documents/upload`：multipart form 字段。
- `POST /documents/parse`：JSON request body 字段。
- `GET /documents`、`GET /documents/content`、`GET /documents/file`：query 参数。
- `POST /rag/documents/upload`：multipart form 字段。
- `POST /rag/documents/{doc_id}/ingest`、`DELETE /rag/documents/{doc_id}`：query 参数。
- `POST /documents/{doc_id}/enrichment/retry`：query 参数。

文档、parent/child/table/OCR chunk、FTS 和向量记录必须与请求 scope 同域。跨库 document/chunk 身份会被拒绝。

## 查询与聊天范围

`POST /rag/query` 与 `POST /chat/stream` 支持：

```json
{
  "question": "问题文本",
  "knowledge_base_id": "kb-a",
  "knowledge_base_ids": ["kb-a", "kb-b"]
}
```

客户端通常二选一；`knowledge_base_ids` 用于多库 fan-out。服务验证所有 KB 处于 active 且属于同一 workspace，检索在排序前过滤 scope，并在 citation、父块和图谱 source chunk 回查时再次校验。未传任一字段时使用默认 KB，并在 debug metadata 中记录 `compatibility_default=true`。

`/rag/query` 返回 `answer`、`citations`、`graph_paths`、`used_entities`、`used_chunks`、`confidence` 和 `debug_info`。启用 Agent workflow 时还返回 `agent_trace`、`tool_calls` 和 `evidence_summary`。`/chat/stream` 保留原 SSE framing，并可在答案 token 前发送同类可审计事件。

## 反馈与审计

`POST /feedback` 必须落到一个明确活动 KB。多库回答需要额外提供单个 `knowledge_base_id` 作为修正目标，否则请求被拒绝。查询和反馈分别写入范围化 `query_log` 与 `answer_feedback`，记录实际 KB scope、工具和引用 chunk，但审计记录不作为知识证据。

## reset_required

破坏性 clean-rebuild 没有 HTTP API。旧 SQLite schema、maintenance marker 或不兼容 Milvus collection 会使启动或证据访问失败关闭；运维人员必须停服务后运行 `python -m app.scripts.rebuild_knowledge_storage`。正常 HTTP 请求不能绕过、确认或触发全局清空。
