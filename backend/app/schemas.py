from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    memory_enabled: bool = True
    temporary: bool = False
    knowledge_base_id: str | None = None
    knowledge_base_ids: list[str] | None = None
    chat_mode: Literal["quick", "reasoning"] | None = None
    attachment_ids: list[str] | None = None


class ChatAttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str = ""
    size: int
    status: str
    created_at: str
    expires_at: str
    parse_error: str | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: str = ""
    type: str = "document"
    workspace_id: str | None = None
    indexing_strategy: dict = Field(default_factory=dict)
    provider_config: dict = Field(default_factory=dict)


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    indexing_strategy: dict | None = None
    provider_config: dict | None = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str = ""
    type: str = "document"
    status: str = "active"
    indexing_strategy: dict = Field(default_factory=dict)
    provider_config: dict = Field(default_factory=dict)
    aggregate: dict = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class KnowledgeBasesResponse(BaseModel):
    items: list[KnowledgeBaseResponse] = Field(default_factory=list)


class IngestResponse(BaseModel):
    files: int
    chunks: int


class DocumentUploadResponse(BaseModel):
    doc_id: str
    source: str
    filename: str
    size: int
    parse_status: str = "parsed"
    chunks: int = 0
    error: str | None = None


class UploadBatchCreateRequest(BaseModel):
    settings: dict = Field(default_factory=dict)


class UploadBatchSettingsUpdateRequest(BaseModel):
    settings: dict = Field(default_factory=dict)


class UploadBatchFileTaskResponse(BaseModel):
    id: str
    batch_id: str
    workspace_id: str
    knowledge_base_id: str
    original_name: str
    relative_path: str
    storage_path: str = ""
    size: int = 0
    status: str
    document_id: str | None = None
    chunks: int = 0
    error_message: str = ""
    phases: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    retry_eligible: bool = False
    created_at: str = ""
    updated_at: str = ""


class UploadBatchResponse(BaseModel):
    id: str
    workspace_id: str
    knowledge_base_id: str
    status: str
    settings: dict = Field(default_factory=dict)
    effective_settings: dict = Field(default_factory=dict)
    aggregate: dict = Field(default_factory=dict)
    files: list[UploadBatchFileTaskResponse] = Field(default_factory=list)
    error_message: str = ""
    created_at: str = ""
    updated_at: str = ""
    confirmed_at: str | None = None
    completed_at: str | None = None


class DocumentParseRequest(BaseModel):
    source: str
    knowledge_base_id: str | None = None


class DocumentParseResponse(BaseModel):
    doc_id: str
    source: str
    extension: str
    characters: int
    parent_chunks: int
    child_chunks: int
    table_chunks: int = 0
    preview: str
    parser_diagnostics: dict = Field(default_factory=dict)
    document_metadata: dict = Field(default_factory=dict)
    chunk_diagnostics: dict = Field(default_factory=dict)
    chunk_statistics: dict = Field(default_factory=dict)
    chunk_previews: list[dict] = Field(default_factory=list)


class SourceHit(BaseModel):
    source: str
    score: float


class DocumentContentResponse(BaseModel):
    source: str
    content: str


class DocumentItem(BaseModel):
    id: str
    workspace_id: str = ""
    knowledge_base_id: str = ""
    name: str
    file_type: str
    storage_path: str
    parse_status: str
    created_at: str
    updated_at: str
    metadata_json: dict = {}
    chunks: int = 0
    source: str = ""
    size: int = 0
    summary: str = ""
    keywords_json: list[str] = Field(default_factory=list)
    suggested_questions_json: list[str] = Field(default_factory=list)
    summary_status: str = "none"
    summary_error: str = ""
    summary_model_ref: str = ""
    summary_generated_at: str | None = None
    summary_version: int = 0
    summary_available: bool = False
    processing_task_id: str = ""
    processing_task_status: str = ""
    processing_task_attempt: int = 0
    processing_task_max_attempts: int = 0
    processing_dead_lettered: bool = False
    processing_last_error: str = ""
    processing_latest_attempt: int = 0


class DocumentsResponse(BaseModel):
    items: list[DocumentItem]


class FeedbackCreateRequest(BaseModel):
    question: str
    answer: str
    knowledge_base_id: str | None = None
    knowledge_base_ids: list[str] | None = None


class FeedbackCreateResponse(BaseModel):
    title: str
    source: str
    chunks: int


class MemoryItem(BaseModel):
    id: str
    scope: str
    type: str
    content: str
    confidence: float
    status: str = "active"
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoriesResponse(BaseModel):
    items: list[MemoryItem]


class MemoryDeleteResponse(BaseModel):
    id: str
    status: str


class RagDocumentUploadResponse(BaseModel):
    doc_id: str
    status: str


class RagDocumentIngestResponse(BaseModel):
    doc_id: str
    parse_status: str
    chunk_count: int
    vector_count: int


class RagQueryRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None
    top_k: int = 8
    filters: dict = {}
    knowledge_base_id: str | None = None
    knowledge_base_ids: list[str] | None = None


class RagQueryResponse(BaseModel):
    answer: str
    citations: list = []
    used_chunks: list = []
    used_entities: list = []
    graph_paths: list = []
    confidence: float = 0.0
    agent_trace: list = []
    tool_calls: list = []
    evidence_summary: dict = {}
    debug_info: dict | None = None


class RagDeleteResponse(BaseModel):
    doc_id: str
    status: str


class EvalRunCreateRequest(BaseModel):
    dataset_path: str
    case_ids: list[str] | None = None
    baseline_run_id: str | None = None


class EvalRunResponse(BaseModel):
    id: str
    status: str
    dataset_id: str = ""
    dataset_version: str = ""
    dataset_path: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    aggregate_scores: dict = {}
    report_paths: dict = {}
    error_message: str = ""


class EvalRunsResponse(BaseModel):
    items: list[EvalRunResponse]


class EvalResultResponse(BaseModel):
    id: str | None = None
    run_id: str
    case_id: str
    status: str
    question: str = ""
    query_type: str = ""
    tags: list = []
    answer: str = ""
    metric_scores: dict = {}
    latency_ms: float = 0.0
    error_message: str = ""
    response_snapshot: dict = {}
    evidence_snapshot: dict = {}


class EvalResultsResponse(BaseModel):
    items: list[EvalResultResponse]
