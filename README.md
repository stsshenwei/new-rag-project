# New RAG Project

一个面向企业知识库问答的全栈 RAG 系统。项目使用 Next.js 构建前端交互界面，FastAPI 承载文档处理、检索、智能推理、流式回答、知识库管理和评测能力。

## 项目优势

- **证据优先的回答机制**：回答必须来自检索到的知识库证据；证据不足时明确说明无法确定，减少模型凭空补全。
- **混合检索能力**：支持向量检索、Milvus BM25、SQLite FTS5 关键词检索、RRF 融合、可选重排和父块召回，兼顾语义召回与精确匹配。
- **智能推理检索**：Reasoning 模式可先用关键词锚定实体和同义表达，再进行语义扩展，并要求阅读全文证据后再生成最终答案。
- **多知识库隔离**：支持 workspace 与 knowledge base 范围选择，旧客户端未显式传范围时只访问默认知识库，不会误检索全部数据。
- **文档处理可追踪**：上传、解析、切片、索引、OCR/图像处理和后处理阶段都有可审计状态；本地 trace 文件便于定位失败原因。
- **分阶段上传**：文件选择后先进入待处理批次，只有用户确认后才解析、切片、嵌入、索引或调用外部 Provider。
- **产品筛选更稳健**：对“24 个光口交换机”“8 个电口控制器”等规格型问题，检索后会做同源约束过滤，避免把不满足硬性条件的型号混入答案。
- **流式交互体验**：`/chat/stream` 使用 SSE 实时返回来源、执行摘要、回答 token、引用校验和完成事件。
- **可观测与可评测**：支持请求级日志、`X-Trace-ID`、可选 Langfuse、处理 trace、RAG/GraphRAG/Agentic Retrieval 离线评测。
- **安全边界清晰**：上传路径、知识库范围、日志脱敏、引用校验、工具输出和前端执行摘要都有明确边界，避免泄露内部提示词、密钥或非授权文档。

## 技术栈

- Frontend: Next.js App Router
- Backend: FastAPI
- Metadata store: SQLite
- Vector / BM25 store: Milvus
- Keyword fallback: SQLite FTS5
- Optional graph store: Neo4j
- Optional observability: Langfuse
- LLM / embedding provider: OpenAI-compatible API

## 项目结构

```text
new-rag-project/
  frontend/                 Next.js 前端
  backend/                  FastAPI 后端
    app/
      main.py               API 入口与服务装配
      services/             RAG、检索、Agent、知识库、评测等核心服务
      models/               运行时配置与领域模型
    config/prompt_templates/ Prompt 模板
    data/                   默认知识文件、上传文件、反馈文件
    evalsets/               可选评测集
  docs/                     架构、开发、API 与设计文档
  openspec/                 变更设计与规格文档
```

## 快速启动

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

在 `backend/.env` 中至少配置：

```env
OPENAI_API_KEY=your-api-key
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

启动服务：

```powershell
uvicorn app.main:app --reload --port 8000
```

健康检查：

```powershell
curl http://localhost:8000/health
```

### 2. 启动前端

```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

浏览器打开：

```text
http://localhost:3000
```

### 3. 手动入库

将知识文件放入 `backend/data/` 后执行：

```powershell
curl -X POST http://localhost:8000/ingest
```

## 支持的知识文件

默认支持以下文件类型：

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

PDF、Office、表格、Markdown 和 HTML 文档会进入统一的解析、切片、索引流程。大文件和复杂文档建议通过知识库页面的分阶段上传流程处理。

## 核心能力

### 知识库管理

知识库页面支持：

- 创建和管理多个 Document 知识库
- 上传文件或文件夹
- 查看处理状态
- 预览文档
- 按知识库范围发起对话
- 对失败文档进行重试

分阶段上传 API：

- `POST /knowledge-bases/{knowledge_base_id}/upload-batches`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/files`
- `PATCH /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/settings`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/confirm`
- `GET /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/files/{file_id}/retry`
- `POST /knowledge-bases/{knowledge_base_id}/upload-batches/{batch_id}/cancel`

`POST /documents/upload` 仍保留为兼容接口，新知识库管理页面推荐使用分阶段上传 API。

### 检索与回答

默认检索流程：

```text
用户问题
  -> 查询理解与术语扩展
  -> 向量检索 / BM25 / FTS5
  -> RRF 融合与去重
  -> 可选重排
  -> 父块和上下文召回
  -> 规格约束过滤
  -> 构造提示词
  -> 流式生成答案
  -> 引用与证据校验
```

对产品、型号、端口、参数类问题，系统会尽量保证型号、参数、端口数、场景建议来自同一产品或同一来源证据，避免跨文档拼接属性。

### 智能推理模式

Reasoning 模式适合复杂检索、对比、选型、影响分析、故障排查和多轮证据补全。它支持：

- 使用 LLM 生成同义词、别名、英文名、历史名称和动作时间词作为检索提示
- 默认先进行关键词锚定，再进行语义扩展
- 工具返回候选后必须阅读全文或文档信息
- 证据不足时进行有限补救检索
- 对外只展示可审计摘要，不展示隐藏推理链或原始工具参数

相关开关：

```env
AGENT_RUNTIME_ENABLED=true
REASONING_LLM_GREP_FIRST_ENABLED=true
QUICK_LLM_GREP_FIRST_ENABLED=false
AGENT_TRACE_STREAM_ENABLED=true
```

### 流式聊天

前端请求：

```text
POST /chat/stream
```

流式事件包含：

- `conversation_id`
- `sources`
- `reasoning`
- `agent_trace`
- `tool_call`
- `tool_observation`
- `evidence_summary`
- `citation_verification`
- `token`
- `memory_updated`
- `[DONE]`

旧客户端仍可只消费 `sources`、`reasoning`、`token` 和 `[DONE]`。

### 可观测性

后端支持请求级日志，每个响应会带 `X-Trace-ID`：

```env
LOG_LEVEL=debug
LOG_PATH=log/app.log
LOG_FORMAT=%d %level %traceId %msg
```

排查流程：

1. 复现请求。
2. 从响应头复制 `X-Trace-ID`。
3. 在 `backend/log/app.log` 中搜索该 trace id。
4. 查看 `request.start`、组件日志、`request.end` 和同 trace id 的异常堆栈。

日志会脱敏 `Authorization`、cookie、token、API key、password、secret 等敏感字段。二进制上传、文件下载和 SSE 流只记录摘要。

### Langfuse

Langfuse 是可选能力，失败时不会影响本地日志、SQLite 处理 span 和本地 trace 文件：

```env
LANGFUSE_ENABLED=true
LANGFUSE_BASE_URL=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_ENVIRONMENT=local
LANGFUSE_DEBUG=true
```

可通过 `GET /observability/status` 或 `/health` 检查连接状态。

### 企业评测

后端提供可选评测套件，用于回放 RAG、GraphRAG 和 Agentic Retrieval 问题。评测集默认位于 `backend/evalsets`，报告默认写入向量存储目录下的 `eval_reports`。

启动评测：

```powershell
curl -X POST http://localhost:8000/eval/runs `
  -H "Content-Type: application/json" `
  -d "{\"dataset_path\":\"sample_enterprise_eval.json\"}"
```

查看评测：

```powershell
curl http://localhost:8000/eval/runs
curl http://localhost:8000/eval/runs/<run_id>
curl http://localhost:8000/eval/runs/<run_id>/results
```

## 关键配置

```env
DEFAULT_WORKSPACE_ID=default-workspace
DEFAULT_WORKSPACE_NAME=默认工作空间
DEFAULT_KNOWLEDGE_BASE_ID=default-knowledge-base
DEFAULT_KNOWLEDGE_BASE_NAME=默认知识库

METADATA_DB_PATH=./vector_db/rag_metadata.sqlite3
MILVUS_URI=http://127.0.0.1:19530
MILVUS_TOKEN=root:Milvus
MILVUS_COLLECTION=rag_chunk_vectors
MILVUS_BM25_ENABLED=false

PROCESSING_WORKER_ENABLED=false
PROCESSING_TRACE_ENABLED=true
PROCESSING_TRACE_DIR=./data/processing_traces

DOCUMENT_ENRICHMENT_ENABLED=false
DOCUMENT_ENRICHMENT_MODEL=gpt-4o-mini
DOCUMENT_ENRICHMENT_ASYNC=true
DOCUMENT_ENRICHMENT_MAX_BATCH_TOKENS=6000
DOCUMENT_ENRICHMENT_MAX_SUMMARY_CHARS=1200
DOCUMENT_ENRICHMENT_MAX_RETRIES=2

KG_EXTRACTION_ENABLED=false
GRAPH_RETRIEVER_ENABLED=false
AGENTIC_RETRIEVAL_ENABLED=false
CHAT_AGENTIC_WORKFLOW_ENABLED=false
```

## 存储说明

当前活跃 RAG 存储使用 SQLite + Milvus：

- SQLite 保存 `document`、`document_chunk`、FTS5、知识库、任务、反馈、会话和评测元数据。
- Milvus 保存 child/table/OCR chunk 向量，可选启用 BM25。
- Neo4j 是可选图谱存储；关闭时后端不会强依赖 Neo4j driver。
- `backend/chroma_db/` 仅作为历史数据目录保留，除非明确清理，不要手动删除。

## 数据重建

当底层 schema 或存储结构需要重新初始化时，应先停止 API、ingest、worker 和图谱/增强任务，再在 `backend/` 下执行维护命令。

只查看计划，不删除数据：

```powershell
python -m app.scripts.rebuild_knowledge_storage --delete-managed-sources --include-neo4j
```

确认备份后执行：

```powershell
python -m app.scripts.rebuild_knowledge_storage `
  --execute `
  --environment dev `
  --confirm RESET_ALL_APPLICATION_DATA:dev `
  --backup-dir D:\backup\new-rag-project-before-reset `
  --delete-managed-sources `
  --include-neo4j
```

`--backup-dir` 会备份 SQLite 和受管理源文件；Milvus 与 Neo4j 需要先使用各自原生工具备份。维护命令失败时会保留 maintenance 状态并阻止应用启动，排除故障后应重新执行完整 clean-rebuild。

## 开发文档

- [架构说明](docs/ARCHITECTURE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [API 文档](docs/API.md)
- [后端 RAG Pipeline 设计](docs/design-docs/backend-rag-pipeline.md)
