from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_EVAL_SCHEMA_VERSION = "1.0"


@dataclass
class EvalCase:
    id: str
    question: str
    query_type: str = "fact"
    tags: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    knowledge_base_ids: list[str] = field(default_factory=list)
    expected_answer_terms: list[str] = field(default_factory=list)
    expected_source_chunk_ids: list[str] = field(default_factory=list)
    expected_source_doc_ids: list[str] = field(default_factory=list)
    expected_entities: list[str] = field(default_factory=list)
    expected_graph_paths: list[dict[str, Any]] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expect_insufficient_evidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=str(data.get("id") or ""),
            question=str(data.get("question") or ""),
            query_type=str(data.get("query_type") or "fact"),
            tags=list(data.get("tags") or []),
            filters=dict(data.get("filters") or {}),
            knowledge_base_ids=list(data.get("knowledge_base_ids") or ([data["knowledge_base_id"]] if data.get("knowledge_base_id") else [])),
            expected_answer_terms=list(data.get("expected_answer_terms") or []),
            expected_source_chunk_ids=list(data.get("expected_source_chunk_ids") or data.get("expected_sources") or []),
            expected_source_doc_ids=list(data.get("expected_source_doc_ids") or []),
            expected_entities=list(data.get("expected_entities") or []),
            expected_graph_paths=list(data.get("expected_graph_paths") or []),
            expected_tools=list(data.get("expected_tools") or []),
            forbidden_tools=list(data.get("forbidden_tools") or []),
            expect_insufficient_evidence=bool(data.get("expect_insufficient_evidence", False)),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "query_type": self.query_type,
            "tags": list(self.tags),
            "filters": dict(self.filters),
            "knowledge_base_ids": list(self.knowledge_base_ids),
            "expected_answer_terms": list(self.expected_answer_terms),
            "expected_source_chunk_ids": list(self.expected_source_chunk_ids),
            "expected_source_doc_ids": list(self.expected_source_doc_ids),
            "expected_entities": list(self.expected_entities),
            "expected_graph_paths": list(self.expected_graph_paths),
            "expected_tools": list(self.expected_tools),
            "forbidden_tools": list(self.forbidden_tools),
            "expect_insufficient_evidence": self.expect_insufficient_evidence,
            "metadata": dict(self.metadata),
        }


@dataclass
class EvaluationDataset:
    schema_version: str
    id: str
    name: str
    version: str
    cases: list[EvalCase]
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: str = "") -> "EvaluationDataset":
        return cls(
            schema_version=str(data.get("schema_version") or ""),
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            version=str(data.get("version") or ""),
            cases=[EvalCase.from_dict(item) for item in data.get("cases") or []],
            metadata=dict(data.get("metadata") or {}),
            source_path=source_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "metadata": dict(self.metadata),
            "source_path": self.source_path,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass
class MetricScore:
    name: str
    score: float
    passed: bool
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(float(self.score), 4),
            "passed": bool(self.passed),
            "summary": self.summary,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetricScore":
        return cls(
            name=str(data.get("name") or ""),
            score=float(data.get("score") or 0.0),
            passed=bool(data.get("passed")),
            summary=str(data.get("summary") or ""),
            details=dict(data.get("details") or {}),
        )


@dataclass
class EvaluationAnswerSnapshot:
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    used_chunks: list[str] = field(default_factory=list)
    used_entities: list[dict[str, Any]] = field(default_factory=list)
    graph_paths: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    debug_info: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    @classmethod
    def from_response(cls, response: dict[str, Any], latency_ms: float = 0.0) -> "EvaluationAnswerSnapshot":
        return cls(
            answer=str(response.get("answer") or ""),
            citations=list(response.get("citations") or []),
            used_chunks=list(response.get("used_chunks") or []),
            used_entities=list(response.get("used_entities") or []),
            graph_paths=list(response.get("graph_paths") or []),
            confidence=float(response.get("confidence") or 0.0),
            agent_trace=_scrub_private_fields(list(response.get("agent_trace") or [])),
            tool_calls=_scrub_private_fields(list(response.get("tool_calls") or [])),
            evidence_summary=_scrub_private_fields(dict(response.get("evidence_summary") or {})),
            debug_info=_scrub_private_fields(dict(response.get("debug_info") or {})),
            latency_ms=float(latency_ms or 0.0),
        )

    def to_response_snapshot(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": list(self.citations),
            "used_chunks": list(self.used_chunks),
            "used_entities": list(self.used_entities),
            "graph_paths": list(self.graph_paths),
            "confidence": self.confidence,
            "agent_trace": _scrub_private_fields(self.agent_trace),
            "tool_calls": _scrub_private_fields(self.tool_calls),
            "evidence_summary": _scrub_private_fields(self.evidence_summary),
            "debug_info": _scrub_private_fields(self.debug_info),
        }

    def to_evidence_snapshot(self) -> dict[str, Any]:
        return {
            "citations": list(self.citations),
            "used_chunks": list(self.used_chunks),
            "used_entities": list(self.used_entities),
            "graph_paths": list(self.graph_paths),
            "tool_calls": list(self.tool_calls),
        }


@dataclass
class EvalRunRecord:
    id: str
    dataset_id: str
    dataset_version: str
    dataset_path: str
    status: str = "running"
    started_at: str = ""
    finished_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    aggregate_scores: dict[str, Any] = field(default_factory=dict)
    report_paths: dict[str, str] = field(default_factory=dict)
    error_message: str = ""
    knowledge_base_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalRunRecord":
        return cls(**data)


@dataclass
class EvalResultRecord:
    run_id: str
    case_id: str
    status: str
    question: str
    query_type: str = "fact"
    tags: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)
    case_snapshot: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    response_snapshot: dict[str, Any] = field(default_factory=dict)
    evidence_snapshot: dict[str, Any] = field(default_factory=dict)
    metric_scores: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error_message: str = ""
    id: str | None = None
    created_at: str = ""


@dataclass
class EvaluationReportMetadata:
    run_id: str
    json_path: str = ""
    markdown_path: str = ""
    aggregate_scores: dict[str, Any] = field(default_factory=dict)
    regression_summary: dict[str, Any] = field(default_factory=dict)


def _scrub_private_fields(value: Any) -> Any:
    private_keys = {"chain_of_thought", "scratchpad", "private_reasoning", "memory_context", "raw_prompt"}
    if isinstance(value, dict):
        return {key: _scrub_private_fields(item) for key, item in value.items() if key not in private_keys}
    if isinstance(value, list):
        return [_scrub_private_fields(item) for item in value]
    return value
