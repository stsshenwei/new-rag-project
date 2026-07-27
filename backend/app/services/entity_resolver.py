import re
from typing import Protocol

from app.models.kg_models import Entity, generated_id


class EntityVectorProvider(Protocol):
    def upsert_entities(self, entities: list[Entity]) -> None:
        ...

    def search_similar(self, entity: Entity, top_k: int = 3) -> list[dict]:
        ...


class EntityResolverProvider(Protocol):
    def resolve(self, entity: Entity) -> Entity:
        ...


def normalize_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def stable_entity_id(entity_type: str, name: str) -> str:
    return f"entity-{generated_id(entity_type, normalize_entity_name(name))}"


class BaselineEntityResolver:
    def __init__(
        self,
        existing_entities: list[Entity] | None = None,
        entity_vector_provider: EntityVectorProvider | None = None,
        similarity_threshold: float = 0.92,
    ):
        self.entity_vector_provider = entity_vector_provider
        self.similarity_threshold = similarity_threshold
        self.entities_by_id: dict[str, Entity] = {}
        for entity in existing_entities or []:
            self.entities_by_id[entity.id] = entity

    def resolve(self, entity: Entity) -> Entity:
        exact = self._find_exact_or_alias(entity)
        if exact:
            return exact
        vector_match = self._find_vector_match(entity)
        if vector_match:
            self.entities_by_id[vector_match.id] = vector_match
            return vector_match
        canonical = Entity(
            id=entity.id or stable_entity_id(entity.type, entity.name),
            type=entity.type,
            name=entity.name,
            description=entity.description,
            aliases=entity.aliases,
            confidence=entity.confidence,
            metadata=entity.metadata,
        )
        self.entities_by_id[canonical.id] = canonical
        return canonical

    def _find_exact_or_alias(self, entity: Entity) -> Entity | None:
        needle = normalize_entity_name(entity.name)
        for existing in self.entities_by_id.values():
            if existing.type != entity.type:
                continue
            names = [existing.name, *existing.aliases]
            if needle in {normalize_entity_name(name) for name in names}:
                return existing
        return None

    def _find_vector_match(self, entity: Entity) -> Entity | None:
        if self.entity_vector_provider is None:
            return None
        for match in self.entity_vector_provider.search_similar(entity, top_k=3):
            matched = match.get("entity")
            score = float(match.get("score", 0.0))
            if isinstance(matched, Entity) and matched.type == entity.type and score >= self.similarity_threshold:
                return matched
        return None
