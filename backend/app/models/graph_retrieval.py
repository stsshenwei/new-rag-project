from dataclasses import dataclass, field
from typing import Any

from app.models.kg_models import Entity, GraphPath, Relation


@dataclass(frozen=True)
class GraphRetrievalResult:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    paths: list[GraphPath] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence_chunks: list[dict[str, Any]] = field(default_factory=list)
    debug_info: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphContext:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    paths: list[GraphPath] = field(default_factory=list)
    path_descriptions: list[str] = field(default_factory=list)
    source_chunk_ids: list[str] = field(default_factory=list)
    evidence_chunks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    debug_info: dict[str, Any] = field(default_factory=dict)
