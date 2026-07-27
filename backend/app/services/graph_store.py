import json
import re
from typing import Any, Protocol

from app.models.kg_models import ALLOWED_ENTITY_TYPES, GraphPath, Entity, Relation
from app.models.knowledge_base import KnowledgeBaseScope


class GraphStoreProvider(Protocol):
    def upsert_entity(self, entity: Entity) -> None:
        ...

    def upsert_relation(self, relation: Relation) -> None:
        ...

    def close(self) -> None:
        ...


class UnavailableGraphStore:
    def __init__(self, reason: str):
        self.reason = reason

    def upsert_entity(self, entity: Entity) -> None:
        raise RuntimeError(self.reason)

    def upsert_relation(self, relation: Relation) -> None:
        raise RuntimeError(self.reason)

    def close(self) -> None:
        return None


def _safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value)
    if not cleaned:
        raise ValueError("Neo4j label cannot be empty")
    return cleaned


class Neo4jGraphStore:
    def __init__(self, uri: str, auth: tuple[str, str], driver_factory=None):
        if driver_factory is None:
            try:
                from neo4j import GraphDatabase
            except Exception as exc:
                raise RuntimeError("Neo4j graph store requires the optional neo4j driver.") from exc
            driver_factory = GraphDatabase.driver
        self._driver = driver_factory(uri, auth=auth)

    def upsert_entity(self, entity: Entity) -> None:
        label = _safe_label(entity.type)
        query = f"""
        MERGE (e:Entity:{label} {{id: $id}})
        SET e.name = $name,
            e.entity_type = $entity_type,
            e.description = $description,
            e.aliases = $aliases,
            e.confidence = $confidence,
            e.metadata = $metadata,
            e.scope_keys = CASE
                WHEN $scope_key = '' OR $scope_key IN coalesce(e.scope_keys, []) THEN coalesce(e.scope_keys, [])
                ELSE coalesce(e.scope_keys, []) + $scope_key
            END
        """
        with self._driver.session() as session:
            session.run(
                query,
                id=entity.id,
                name=entity.name,
                entity_type=entity.type,
                description=entity.description,
                aliases=entity.aliases,
                confidence=entity.confidence,
                metadata=entity.metadata,
                scope_key=_scope_key_from_metadata(entity.metadata),
            )

    def upsert_relation(self, relation: Relation) -> None:
        relation_type = _safe_label(relation.relation_type)
        query = f"""
        MATCH (source:Entity {{id: $source_entity_id}})
        MATCH (target:Entity {{id: $target_entity_id}})
        MERGE (source)-[r:{relation_type} {{
            source_chunk_id: $source_chunk_id,
            doc_id: $doc_id,
            extractor_version: $extractor_version
        }}]->(target)
        SET r.description = $description,
            r.confidence = $confidence,
            r.page_start = $page_start,
            r.page_end = $page_end,
            r.created_at = $created_at,
            r.metadata = $metadata,
            r.workspace_id = $workspace_id,
            r.knowledge_base_id = $knowledge_base_id
        """
        with self._driver.session() as session:
            session.run(
                query,
                source_entity_id=relation.source_entity_id,
                target_entity_id=relation.target_entity_id,
                description=relation.description,
                confidence=relation.confidence,
                source_chunk_id=relation.source_chunk_id,
                doc_id=relation.doc_id,
                page_start=relation.page_start,
                page_end=relation.page_end,
                extractor_version=relation.extractor_version,
                created_at=relation.created_at,
                metadata=relation.metadata,
                workspace_id=str(relation.metadata.get("workspace_id", "")),
                knowledge_base_id=str(relation.metadata.get("knowledge_base_id", "")),
            )

    def search_entities(
        self,
        query: str,
        limit: int = 10,
        entity_types: set[str] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        allowed_types = sorted((entity_types or ALLOWED_ENTITY_TYPES) & ALLOWED_ENTITY_TYPES)
        scope_clause = "AND any(scope_key IN coalesce(e.scope_keys, []) WHERE scope_key IN $scope_keys)" if scope else ""
        cypher = """
        MATCH (e:Entity)
        WHERE e.entity_type IN $entity_types
          {scope_clause}
          AND (
            toLower(e.name) CONTAINS toLower($search_text)
            OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) CONTAINS toLower($search_text))
            OR e.id = $search_text
          )
        RETURN e AS entity,
               CASE
                 WHEN e.id = $search_text THEN 1.0
                 WHEN toLower(e.name) = toLower($search_text) THEN 0.95
                 ELSE 0.85
               END AS score
        ORDER BY score DESC, e.name ASC
        LIMIT $limit
        """.format(scope_clause=scope_clause)
        with self._driver.session() as session:
            rows = session.run(
                cypher,
                search_text=query,
                limit=limit,
                entity_types=allowed_types,
                scope_keys=_scope_keys(scope),
            )
            return [
                {"entity": entity, "score": float(row.get("score", entity.confidence))}
                for row in rows
                if (entity := _entity_from_record(row.get("entity"))) is not None
            ]

    def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
        limit: int = 20,
        scope: KnowledgeBaseScope | None = None,
    ) -> dict[str, Any]:
        depth = max(1, min(5, int(depth)))
        scope_clause = (
            "WHERE all(rel IN relationships(path) WHERE rel.workspace_id = $workspace_id AND rel.knowledge_base_id IN $knowledge_base_ids)"
            if scope
            else ""
        )
        cypher = f"""
        MATCH path = (source:Entity {{id: $entity_id}})-[*1..{depth}]-(neighbor:Entity)
        {scope_clause}
        WITH path
        LIMIT $limit
        RETURN [node IN nodes(path) | node] AS entities,
               [rel IN relationships(path) | {{
                   source_entity_id: startNode(rel).id,
                   target_entity_id: endNode(rel).id,
                   relation_type: type(rel),
                   description: rel.description,
                   confidence: rel.confidence,
                   source_chunk_id: rel.source_chunk_id,
                   doc_id: rel.doc_id,
                   page_start: rel.page_start,
                   page_end: rel.page_end,
                   extractor_version: rel.extractor_version,
                   created_at: rel.created_at,
                   metadata: rel.metadata
               }}] AS relations
        """
        with self._driver.session() as session:
            rows = session.run(
                cypher,
                entity_id=entity_id,
                limit=limit,
                workspace_id=scope.workspace_id if scope else "",
                knowledge_base_ids=list(scope.selected_knowledge_base_ids) if scope else [],
            )
            return _rows_to_graph_result(rows)

    def find_paths(
        self,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 3,
        limit: int = 10,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[GraphPath]:
        max_depth = max(1, min(5, int(max_depth)))
        scope_clause = (
            "WHERE all(rel IN relationships(path) WHERE rel.workspace_id = $workspace_id AND rel.knowledge_base_id IN $knowledge_base_ids)"
            if scope
            else ""
        )
        cypher = f"""
        MATCH path = (source:Entity {{id: $source_entity_id}})-[*1..{max_depth}]-(target:Entity {{id: $target_entity_id}})
        {scope_clause}
        WITH path
        LIMIT $limit
        RETURN [node IN nodes(path) | node] AS entities,
               [rel IN relationships(path) | {{
                   source_entity_id: startNode(rel).id,
                   target_entity_id: endNode(rel).id,
                   relation_type: type(rel),
                   description: rel.description,
                   confidence: rel.confidence,
                   source_chunk_id: rel.source_chunk_id,
                   doc_id: rel.doc_id,
                   page_start: rel.page_start,
                   page_end: rel.page_end,
                   extractor_version: rel.extractor_version,
                   created_at: rel.created_at,
                   metadata: rel.metadata
               }}] AS relations
        """
        paths: list[GraphPath] = []
        with self._driver.session() as session:
            rows = session.run(
                cypher,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                limit=limit,
                workspace_id=scope.workspace_id if scope else "",
                knowledge_base_ids=list(scope.selected_knowledge_base_ids) if scope else [],
            )
            for row in rows:
                entities = [entity for entity in (_entity_from_record(item) for item in row.get("entities", [])) if entity is not None]
                relations = [relation for relation in (_relation_from_record(item) for item in row.get("relations", [])) if relation is not None]
                if not relations:
                    continue
                source_chunk_ids = list(dict.fromkeys(relation.source_chunk_id for relation in relations if relation.source_chunk_id))
                confidence = max((relation.confidence for relation in relations), default=0.0)
                paths.append(GraphPath(entities=entities, relations=relations, source_chunk_ids=source_chunk_ids, confidence=confidence))
        return paths

    def close(self) -> None:
        close = getattr(self._driver, "close", None)
        if callable(close):
            close()


def _rows_to_graph_result(rows: Any) -> dict[str, Any]:
    entities: list[Entity] = []
    relations: list[Relation] = []
    for row in rows:
        entities.extend(entity for entity in (_entity_from_record(item) for item in row.get("entities", [])) if entity is not None)
        relations.extend(relation for relation in (_relation_from_record(item) for item in row.get("relations", [])) if relation is not None)
    return {"entities": entities, "relations": relations}


def _scope_key_from_metadata(metadata: dict[str, Any]) -> str:
    workspace_id = str(metadata.get("workspace_id", "")).strip()
    knowledge_base_id = str(metadata.get("knowledge_base_id", "")).strip()
    return f"{workspace_id}:{knowledge_base_id}" if workspace_id and knowledge_base_id else ""


def _scope_keys(scope: KnowledgeBaseScope | None) -> list[str]:
    if scope is None:
        return []
    return [f"{scope.workspace_id}:{knowledge_base_id}" for knowledge_base_id in scope.selected_knowledge_base_ids]


def _entity_from_record(raw: Any) -> Entity | None:
    if isinstance(raw, Entity):
        return raw
    entity_type = str(_record_get(raw, "entity_type") or _record_get(raw, "type") or "")
    if entity_type not in ALLOWED_ENTITY_TYPES:
        return None
    aliases = _decode_jsonish(_record_get(raw, "aliases"), default=[])
    metadata = _decode_jsonish(_record_get(raw, "metadata"), default={})
    return Entity(
        id=str(_record_get(raw, "id") or _record_get(raw, "entity_id") or ""),
        type=entity_type,
        name=str(_record_get(raw, "name") or _record_get(raw, "entity_name") or ""),
        description=str(_record_get(raw, "description") or ""),
        aliases=list(aliases or []),
        confidence=float(_record_get(raw, "confidence") or 1.0),
        metadata=dict(metadata or {}),
    )


def _relation_from_record(raw: Any) -> Relation | None:
    if isinstance(raw, Relation):
        return raw
    try:
        return Relation(
            source_entity_id=str(_record_get(raw, "source_entity_id") or ""),
            target_entity_id=str(_record_get(raw, "target_entity_id") or ""),
            relation_type=str(_record_get(raw, "relation_type") or _record_get(raw, "type") or ""),
            description=str(_record_get(raw, "description") or ""),
            confidence=float(_record_get(raw, "confidence") or 0.0),
            source_chunk_id=str(_record_get(raw, "source_chunk_id") or ""),
            doc_id=str(_record_get(raw, "doc_id") or ""),
            page_start=_record_get(raw, "page_start"),
            page_end=_record_get(raw, "page_end"),
            extractor_version=str(_record_get(raw, "extractor_version") or ""),
            created_at=str(_record_get(raw, "created_at") or ""),
            metadata=dict(_decode_jsonish(_record_get(raw, "metadata"), default={}) or {}),
        )
    except Exception:
        return None


def _record_get(raw: Any, key: str) -> Any:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get(key)
    get = getattr(raw, "get", None)
    if callable(get):
        return get(key)
    return getattr(raw, key, None)


def _decode_jsonish(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default
