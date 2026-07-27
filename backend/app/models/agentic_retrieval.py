from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


QUESTION_TYPES = {
    "fact",
    "source",
    "howto",
    "troubleshooting",
    "comparison",
    "impact",
    "dependency",
    "summary",
    "decision",
}

TOOL_RAW_RAG = "RawRAGTool"
TOOL_KEYWORD_SEARCH = "KeywordSearchTool"
TOOL_GRAPH_RETRIEVER = "GraphRetrieverTool"
APPROVED_TOOLS = {TOOL_RAW_RAG, TOOL_KEYWORD_SEARCH, TOOL_GRAPH_RETRIEVER}

AGENT_STATES = [
    "AnalyzeQuestion",
    "PlanRetrieval",
    "CheckPermissionScope",
    "RunRetrieval",
    "FuseEvidence",
    "RerankEvidence",
    "NeedMoreEvidence",
    "BuildContext",
    "GenerateAnswer",
    "VerifyCitations",
    "ReturnAnswer",
]


@dataclass
class AgenticRetrievalConfig:
    enabled: bool = False
    chat_stream_enabled: bool = False
    trace_stream_enabled: bool = False
    max_tool_calls: int = 6
    tool_timeout_seconds: float = 10.0
    raw_top_k: int = 8
    keyword_top_k: int = 8
    graph_top_k: int = 8
    graph_max_depth: int = 3


@dataclass
class QueryRoute:
    question_type: str
    confidence: float = 1.0
    detected_entities: list[str] = field(default_factory=list)
    requested_sources: list[str] = field(default_factory=list)
    graph_intent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type,
            "confidence": self.confidence,
            "detected_entities": list(self.detected_entities),
            "requested_sources": list(self.requested_sources),
            "graph_intent": self.graph_intent,
            "metadata": dict(self.metadata),
        }


@dataclass
class PlannedTool:
    name: str
    action: str = "search"
    required: bool = False
    limits: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action": self.action,
            "required": self.required,
            "limits": dict(self.limits),
            "metadata": dict(self.metadata),
        }


@dataclass
class RetrievalPlan:
    question_type: str
    tools: list[PlannedTool]
    max_tool_calls: int = 6
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type,
            "tools": [tool.to_dict() for tool in self.tools],
            "max_tool_calls": self.max_tool_calls,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentTraceStep:
    stage: str
    status: str
    summary: str
    tool: str = ""
    source_chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        safe_metadata = {
            key: value
            for key, value in self.metadata.items()
            if key not in {"chain_of_thought", "scratchpad", "private_reasoning"}
        }
        return {
            "stage": self.stage,
            "status": self.status,
            "summary": self.summary,
            "tool": self.tool,
            "source_chunk_ids": list(dict.fromkeys(self.source_chunk_ids)),
            "metadata": safe_metadata,
        }


@dataclass
class ToolCallRecord:
    tool: str
    action: str
    status: str
    input_summary: str
    output_summary: str = ""
    source_chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "action": self.action,
            "status": self.status,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "source_chunk_ids": list(dict.fromkeys(self.source_chunk_ids)),
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentStreamEvent:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        safe_payload = _scrub_private_fields(self.payload)
        return {"event_type": self.event_type, "payload": safe_payload}

    def to_sse_payload(self) -> dict[str, Any]:
        safe_payload = _scrub_private_fields(self.payload)
        return {self.event_type: safe_payload}


@dataclass
class EvidenceItem:
    id: str
    source_tool: str
    content: str = ""
    chunk_id: str = ""
    doc_id: str = ""
    parent_id: str = ""
    score: float = 0.0
    citation: dict[str, Any] | None = None
    entity: dict[str, Any] | None = None
    graph_path: dict[str, Any] | None = None
    source_chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_tool": self.source_tool,
            "content": self.content,
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "parent_id": self.parent_id,
            "score": self.score,
            "citation": self.citation,
            "entity": self.entity,
            "graph_path": self.graph_path,
            "source_chunk_ids": list(dict.fromkeys(self.source_chunk_ids)),
            "metadata": dict(self.metadata),
        }


def _scrub_private_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _scrub_private_fields(item)
            for key, item in value.items()
            if key not in {"chain_of_thought", "scratchpad", "private_reasoning", "memory_context", "raw_prompt"}
        }
    if isinstance(value, list):
        return [_scrub_private_fields(item) for item in value]
    return value


@dataclass
class EvidenceBundle:
    items: list[EvidenceItem] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    used_chunks: list[str] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    graph_paths: list[dict[str, Any]] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "citations": list(self.citations),
            "used_chunks": list(dict.fromkeys(self.used_chunks)),
            "entities": list(self.entities),
            "relations": list(self.relations),
            "graph_paths": list(self.graph_paths),
            "source_chunk_ids": list(dict.fromkeys(self.source_chunk_ids)),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


@dataclass
class ToolResult:
    tool: str
    action: str
    status: str
    evidence: EvidenceBundle
    observation: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    valid: bool
    verified_citations: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    verified_chunks: list[str] = field(default_factory=list)
    invalid_chunks: list[str] = field(default_factory=list)
    invalid_graph_source_chunks: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "verified_citations": list(self.verified_citations),
            "invalid_citations": list(self.invalid_citations),
            "verified_chunks": list(self.verified_chunks),
            "invalid_chunks": list(self.invalid_chunks),
            "invalid_graph_source_chunks": list(self.invalid_graph_source_chunks),
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }
