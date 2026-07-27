import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


ALLOWED_ENTITY_TYPES = {
    "Document",
    "Chunk",
    "System",
    "Service",
    "Module",
    "API",
    "Database",
    "Middleware",
    "Config",
    "Command",
    "Error",
    "Vulnerability",
    "Version",
    "Person",
    "Team",
    "Concept",
    "Tool",
    "Skill",
    "Agent",
    "KnowledgeBase",
}

ALLOWED_RELATION_TYPES = {
    "HAS_CHUNK",
    "MENTIONS",
    "CONTAINS",
    "BELONGS_TO",
    "DEPENDS_ON",
    "CALLS",
    "USES",
    "CONFIGURES",
    "CAUSES",
    "FIXES",
    "RELATED_TO",
    "AFFECTS",
    "OWNED_BY",
    "HAS_VERSION",
    "EVIDENCED_BY",
    "GENERATED_FROM",
}


def _validate_type(value: str, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        raise ValueError(f"Unsupported {field_name}: {value}")
    return value


def generated_id(*parts: str) -> str:
    raw = "::".join(part.strip().lower() for part in parts if part is not None)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_type(self.type, ALLOWED_ENTITY_TYPES, "entity type")


@dataclass(frozen=True)
class EntityMention:
    id: str
    entity_id: str
    entity_type: str
    entity_name: str
    doc_id: str
    chunk_id: str
    parent_id: str
    page_start: int | None
    page_end: int | None
    mention_text: str
    confidence: float
    created_at: str = ""
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_type(self.entity_type, ALLOWED_ENTITY_TYPES, "entity type")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now().isoformat(timespec="seconds"))


@dataclass(frozen=True)
class Relation:
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    description: str = ""
    confidence: float = 1.0
    source_chunk_id: str = ""
    doc_id: str = ""
    page_start: int | None = None
    page_end: int | None = None
    extractor_version: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_type(self.relation_type, ALLOWED_RELATION_TYPES, "relation type")
        missing = [
            name
            for name in ["source_chunk_id", "doc_id", "extractor_version"]
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Relation missing evidence fields: {', '.join(missing)}")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now().isoformat(timespec="seconds"))


@dataclass(frozen=True)
class GraphPath:
    entities: list[Entity]
    relations: list[Relation]
    source_chunk_ids: list[str]
    confidence: float


@dataclass(frozen=True)
class KGExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
