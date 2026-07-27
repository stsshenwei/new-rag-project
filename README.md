# RAG Fullstack (Next.js + FastAPI)

文档处理默认使用 WeKnora 风格的 `builtin` 混合 PDF 解析（`pypdfium2`）和自适应切片，自动降级顺序固定为 `heading -> heuristic -> legacy/recursive`。

主要配置：`PARSER_ENGINE=builtin`、`PDF_FORCE_SCANNED=false`、`PDF_RENDER_DPI=200`、`PDF_JPEG_QUALITY=90`、`PDF_MAX_PAGES=1000`、`CHUNK_STRATEGY=auto`、`PARENT_CHUNK_SIZE_CHARS=4096`、`CHILD_CHUNK_SIZE_CHARS=384`、`CHILD_CHUNK_OVERLAP_CHARS=76`。

新架构不读取或迁移旧版数据库。技术切换时必须通过带环境确认的维护命令一次性删除全部 SQLite、FTS、Milvus、Neo4j 和旧媒体数据。

## Knowledge Management Staged Upload

The knowledge management page uses a staged upload workflow. Selecting files or folders only opens a pending upload dialog; it does not parse, index, embed, enrich, or call external providers until the user confirms processing.

Staged upload endpoints:

- `POST /knowledge-bases/{knowledge_base_id}/upload-batches`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/files`
- `PATCH /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/settings`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/confirm`
- `GET /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/files/{file_id}/retry`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/cancel`

Document workspace filters are available on `GET /documents`: `knowledge_base_id`, `q`, `tag`, `file_type`, `status`, `source`, `created_from`, and `created_to`.

`POST /documents/upload` remains as a legacy compatibility shortcut. New knowledge-management UI uploads should use the staged endpoints.

## Weknora-Aligned Processing Runtime

Core document processing now has an optional durable worker:

```env
PROCESSING_WORKER_ENABLED=false
PROCESSING_WORKER_ID=local-processing-worker
PROCESSING_WORKER_POLL_INTERVAL_SECONDS=1.0
PROCESSING_WORKER_LEASE_TIMEOUT_SECONDS=300
PROCESSING_WORKER_DEFAULT_MAX_ATTEMPTS=3
PROCESSING_WORKER_RETRY_BACKOFF_SECONDS=10,30,120
PROCESSING_TRACE_ENABLED=true
PROCESSING_TRACE_DIR=./data/processing_traces
```

When the worker is enabled, upload confirmation writes durable `document_processing_task` rows first, then the worker performs parsing, chunking, vector indexing, multimodal processing, and postprocess work with retries and dead-letter records. When disabled, upload confirmation keeps the existing FastAPI background-task compatibility path.

The Trace drawer reads SQLite `knowledge_processing_spans` as the primary root/stage/subspan/generation tree. Local files such as `report.md`, `parsed.md`, `chunks.jsonl`, and `chunks_preview.md` are supplemental evidence for manual debugging.

Prompt templates live in `backend/config/prompt_templates/`. Quick answer and intelligent reasoning compose the user question, selected knowledge base, conversation context, retrieved context, tools, and skills through the catalog instead of scattered hardcoded prompts.

## 项目结构

- `frontend`: Next.js 对话助手、知识库目录和范围选择
- `backend`: FastAPI RAG 服务（SQLite + Milvus + 可选 Neo4j + Agentic Retrieval）

## 1) 启动后端

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 填入 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Backend observability logs

The backend can write request-scoped logs to stdout and a file. Each HTTP response includes `X-Trace-ID`; use that value to search the log when a request fails.

```env
LOG_LEVEL=debug
LOG_PATH=log/app.log
LOG_FORMAT=%d %level %traceId %msg
```

PowerShell example:

```powershell
$env:LOG_LEVEL="debug"
$env:LOG_PATH="log/app.log"
$env:LOG_FORMAT="%d %level %traceId %msg"
```

Troubleshooting flow:

1. Reproduce the failing request.
2. Copy `X-Trace-ID` from the response headers.
3. Search `backend/log/app.log` for that trace ID.
4. Inspect `request.start`, component flow logs, `request.end`, and any traceback logged with the same trace ID.

Logs intentionally redact sensitive fields such as `Authorization`, cookies, tokens, API keys, passwords, and secrets. Binary uploads, file downloads, and SSE streams are summarized rather than fully logged.

### Local Langfuse observability

Langfuse is optional and fail-open. Local request logs, SQLite processing spans, and local trace files continue to work when Langfuse is disabled or unreachable. To connect a local Langfuse instance:

```env
LANGFUSE_ENABLED=true
LANGFUSE_BASE_URL=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_ENVIRONMENT=local
LANGFUSE_DEBUG=true
```

`LANGFUSE_BASE_URL` is the preferred local setting. `LANGFUSE_HOST` remains supported as a compatibility alias when `LANGFUSE_BASE_URL` is empty. Check `GET /observability/status` or `/health` to confirm whether the backend sees Langfuse as enabled, configured, package-available, initialized, or failed.

入库（把 `backend/data` 下文件向量化）:

```bash
curl -X POST http://localhost:8000/ingest
```

## 2) 启动前端

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

浏览器打开: `http://localhost:3000`

## 3) 流式交互

- 前端请求 `POST /chat/stream`
- 后端先做向量检索，再拼接提示词调用大模型
- 返回 `text/event-stream`，前端实时拼接 token

## 4) 文档来源

默认读取 `backend/data` 下的:

- `.txt`
- `.md`
- `.html`
- `.csv`
- `.json`
- `.doc`
- `.docx`
- `.xls`
- `.xlsx`
- `.pdf`

## Milvus / Docling storage update

The active RAG store uses SQLite + Milvus:

- SQLite stores `document` and `document_chunk` metadata at `METADATA_DB_PATH` or `./vector_db/rag_metadata.sqlite3`.
- Milvus stores child/table chunk vectors in `MILVUS_COLLECTION` or `rag_chunk_vectors`.
- Milvus connects with `MILVUS_URI` defaulting to `http://127.0.0.1:19530` and `MILVUS_TOKEN` defaulting to `root:Milvus`; do not use `localhost` for the Milvus URI.
- Chroma is legacy data only; do not delete `backend/chroma_db/` unless cleanup is explicitly requested.
- PDF and DOCX parsing prefer Docling. Upload supports PDF, DOCX, HTML, Excel, and Markdown.

## Agentic Retrieval

`/rag/query` now has optional enterprise response fields:

- `agent_trace`
- `tool_calls`
- `evidence_summary`

The feature is default-disabled with `AGENTIC_RETRIEVAL_ENABLED=false`, so existing Raw RAG query behavior stays intact. Enable it to route questions through the finite-state Agentic Retrieval workflow that combines Raw RAG, SQLite FTS5 keyword search, and GraphRetriever evidence with citation verification.

Optional stream trace events are controlled separately with `AGENT_TRACE_STREAM_ENABLED=true`; existing `/chat/stream` SSE events remain compatible.

To make the chat stream itself use the finite-state Agentic Retrieval workflow, enable:

```env
CHAT_AGENTIC_WORKFLOW_ENABLED=true
```

Then `/chat/stream` keeps the old `conversation_id`, `sources`, `reasoning`, `token`, `memory_updated`, and `[DONE]` events, and can additionally emit `agent_trace`, `tool_call`, `tool_observation`, `evidence_summary`, and `citation_verification` events before answer tokens.

## Enterprise Evaluation

The backend includes an optional evaluation suite for replaying curated RAG, GraphRAG, and Agentic Retrieval questions. Evalsets live outside the retrievable corpus, defaulting to `backend/evalsets`, and reports default to the vector-store `eval_reports` directory.

Start a run:

```bash
curl -X POST http://localhost:8000/eval/runs \
  -H "Content-Type: application/json" \
  -d "{\"dataset_path\":\"sample_enterprise_eval.json\"}"
```

Inspect runs:

```bash
curl http://localhost:8000/eval/runs
curl http://localhost:8000/eval/runs/<run_id>
curl http://localhost:8000/eval/runs/<run_id>/results
```

## 多知识库与文档概要

知识管理页现在以 workspace 下的知识库目录为入口，支持创建多个 Document 知识库、进入详情后上传/预览文档、查看处理状态，并从详情页预选知识库开始聊天。

兼容规则：旧客户端未传 `knowledge_base_id` 或 `knowledge_base_ids` 时，只访问 `DEFAULT_KNOWLEDGE_BASE_ID`，不会自动检索全部知识库。

主要配置：

```env
DEFAULT_WORKSPACE_ID=default-workspace
DEFAULT_WORKSPACE_NAME=默认工作空间
DEFAULT_KNOWLEDGE_BASE_ID=default-knowledge-base
DEFAULT_KNOWLEDGE_BASE_NAME=默认知识库
DOCUMENT_ENRICHMENT_ENABLED=false
DOCUMENT_ENRICHMENT_MODEL=gpt-4o-mini
DOCUMENT_ENRICHMENT_ASYNC=true
DOCUMENT_ENRICHMENT_MAX_BATCH_TOKENS=6000
DOCUMENT_ENRICHMENT_MAX_SUMMARY_CHARS=1200
DOCUMENT_ENRICHMENT_MAX_RETRIES=2
```

知识库 API：

- `GET/POST /knowledge-bases`
- `GET/PATCH/DELETE /knowledge-bases/{knowledge_base_id}`
- `POST /knowledge-bases/{knowledge_base_id}/restore`
- `GET /documents?knowledge_base_id=...`
- `POST /documents/{doc_id}/enrichment/retry?knowledge_base_id=...`

文档概要、关键词和建议问题是异步导航 metadata。最终答案和图谱路径仍必须回到原始 `document_chunk`。

### 升级与 clean-rebuild

本次多知识库升级采用最终 schema，不提供旧 SQLite、Milvus、FTS5、KG、评测、反馈或上传数据的迁移/回填。旧 schema 或缺少 workspace/KB 字段的 Milvus collection 会进入 `reset_required`，普通启动、查询和 ingest 都不会自动删除或兼容升级旧数据。

先停止 API、ingest、KG 和 enrichment worker，再在 `backend/` 下执行：

```powershell
# 1. 只显示计划，不删除数据
python -m app.scripts.rebuild_knowledge_storage --delete-managed-sources --include-neo4j

# 2. 确认计划和独立备份后执行
python -m app.scripts.rebuild_knowledge_storage `
  --execute `
  --environment dev `
  --confirm RESET_ALL_APPLICATION_DATA:dev `
  --backup-dir D:\backup\bee-before-reset `
  --delete-managed-sources `
  --include-neo4j
```

`--backup-dir` 备份 SQLite 和受管理文件；Milvus 与 Neo4j 需要先使用各自原生工具备份。命令完成后只创建空的最终 schema、默认 workspace/Document KB、FTS5 和向量 collection，不导入旧记录。部分失败会保留 maintenance 状态并阻止应用启动。完整说明见 [开发指南](docs/DEVELOPMENT.md) 和 [API 文档](docs/API.md)。
