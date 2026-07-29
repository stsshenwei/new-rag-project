import inspect
from typing import Any, Protocol

from app.models.graph_retrieval import GraphContext, GraphRetrievalResult
from app.models.kg_models import ALLOWED_ENTITY_TYPES, ALLOWED_RELATION_TYPES, Entity, GraphPath, Relation
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.kg.entity_resolver import EntityVectorProvider


class GraphQueryProvider(Protocol):
    def search_entities(self, query: str, limit: int = 10, entity_types: set[str] | None = None) -> list[dict[str, Any]]:
        ...

    def get_neighbors(self, entity_id: str, depth: int = 1, limit: int = 20) -> dict[str, Any] | GraphRetrievalResult:
        ...

    def find_paths(self, source_entity_id: str, target_entity_id: str, max_depth: int = 3, limit: int = 10) -> list[Any]:
        ...


class GraphRetriever:
    def __init__(
        self,
        graph_provider: GraphQueryProvider,
        evidence_repository: Any,
        entity_vector_provider: EntityVectorProvider | None = None,
        max_neighbor_depth: int = 3,
        max_path_depth: int = 5,
        entity_limit: int = 10,
        relation_limit: int = 50,
        path_limit: int = 10,
        evidence_chunk_limit: int = 20,
    ):
        self.graph_provider = graph_provider
        self.evidence_repository = evidence_repository
        self.entity_vector_provider = entity_vector_provider
        self.max_neighbor_depth = max(1, max_neighbor_depth)
        self.max_path_depth = max(1, max_path_depth)
        self.entity_limit = max(1, entity_limit)
        self.relation_limit = max(1, relation_limit)
        self.path_limit = max(1, path_limit)
        self.evidence_chunk_limit = max(1, evidence_chunk_limit)

    def entity_search(
        self,
        question: str,
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphRetrievalResult:
        candidates: list[tuple[Entity, float]] = []
        debug_info: dict[str, Any] = {"excluded_entities": []}
        for item in self._provider_call(
            "search_entities",
            question,
            limit=self.entity_limit,
            entity_types=set(ALLOWED_ENTITY_TYPES),
            scope=scope,
        ):
            entity = self._coerce_entity(item.get("entity") if isinstance(item, dict) else item)
            if entity is None:
                debug_info["excluded_entities"].append(item)
                continue
            candidates.append((entity, float(item.get("score", entity.confidence) if isinstance(item, dict) else entity.confidence)))

        if self.entity_vector_provider is not None:
            try:
                query_entity = Entity(id="", type="Concept", name=question)
                search_method = self.entity_vector_provider.search_similar
                if scope is not None and "scope" not in inspect.signature(search_method).parameters:
                    raise RuntimeError("Entity vector provider does not support knowledge-base scope")
                for match in search_method(query_entity, top_k=self.entity_limit, **({"scope": scope} if scope else {})):
                    entity = self._coerce_entity(match.get("entity"))
                    if entity is not None:
                        candidates.append((entity, float(match.get("score", entity.confidence))))
            except Exception as exc:
                debug_info["vector_error"] = str(exc)

        entities, scores = self._dedupe_scored_entities(candidates)
        return GraphRetrievalResult(
            entities=entities[: self.entity_limit],
            confidence=self._confidence(scores),
            debug_info={**debug_info, "knowledge_base_scope": scope.to_dict() if scope else None},
        )

    def neighbor_search(
        self,
        entity_id: str,
        depth: int = 1,
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphRetrievalResult:
        capped_depth = min(max(1, depth), self.max_neighbor_depth)
        raw = self._provider_call(
            "get_neighbors", entity_id, depth=capped_depth, limit=self.relation_limit, scope=scope
        )
        return self._result_from_raw(
            raw,
            debug_info={"requested_depth": depth, "used_depth": capped_depth},
            scope=scope,
        )

    def path_search(
        self,
        source_entity: str,
        target_entity: str,
        max_depth: int = 3,
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphRetrievalResult:
        source_id = self._resolve_entity_id(source_entity, scope)
        target_id = self._resolve_entity_id(target_entity, scope)
        debug_info: dict[str, Any] = {"excluded_paths": [], "source_entity": source_entity, "target_entity": target_entity}
        if not source_id or not target_id:
            debug_info["resolution_failed"] = True
            return GraphRetrievalResult(debug_info=debug_info)
        capped_depth = min(max(1, max_depth), self.max_path_depth)
        raw_paths = self._provider_call(
            "find_paths",
            source_id,
            target_id,
            max_depth=capped_depth,
            limit=self.path_limit,
            scope=scope,
        )
        valid_paths: list[GraphPath] = []
        entities: list[Entity] = []
        relations: list[Relation] = []
        for raw_path in raw_paths[: self.path_limit]:
            path = self._coerce_path(raw_path)
            if path is None:
                debug_info["excluded_paths"].append({"reason": "invalid_path", "path": raw_path})
                continue
            path_result = self._result_from_raw(
                {"entities": path.entities, "relations": path.relations},
                debug_info={"excluded_relations": []},
                scope=scope,
            )
            if not path_result.relations:
                debug_info["excluded_paths"].append({"reason": "missing_evidence", "source_chunk_ids": path.source_chunk_ids})
                continue
            valid_paths.append(
                GraphPath(
                    entities=path_result.entities,
                    relations=path_result.relations,
                    source_chunk_ids=path_result.source_chunk_ids,
                    confidence=path_result.confidence,
                )
            )
            entities.extend(path_result.entities)
            relations.extend(path_result.relations)
        result = self._shape_result(
            entities=entities, relations=relations, paths=valid_paths, debug_info=debug_info, scope=scope
        )
        result.debug_info["used_depth"] = capped_depth
        return result

    def graph_context_build(
        self,
        paths: list[GraphPath],
        entities: list[Entity],
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphContext:
        result = self._shape_result(
            entities=[*entities, *[entity for path in paths for entity in path.entities]],
            relations=[relation for path in paths for relation in path.relations],
            paths=paths,
            debug_info={"context_builder": "graph"},
            scope=scope,
        )
        path_descriptions = [self._describe_path(path) for path in paths]
        return GraphContext(
            entities=result.entities,
            relations=result.relations,
            paths=paths,
            path_descriptions=path_descriptions,
            source_chunk_ids=result.source_chunk_ids,
            evidence_chunks=result.evidence_chunks,
            confidence=result.confidence,
            debug_info=result.debug_info,
        )

    def _resolve_entity_id(self, value: str, scope: KnowledgeBaseScope | None = None) -> str:
        if value.startswith("entity-"):
            return value
        result = self.entity_search(value, scope=scope)
        return result.entities[0].id if result.entities else ""

    def _result_from_raw(
        self,
        raw: dict[str, Any] | GraphRetrievalResult,
        debug_info: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphRetrievalResult:
        if isinstance(raw, GraphRetrievalResult):
            return self._shape_result(
                raw.entities, raw.relations, raw.paths, {**raw.debug_info, **(debug_info or {})}, scope=scope
            )
        return self._shape_result(
            entities=list(raw.get("entities", [])),
            relations=list(raw.get("relations", [])),
            paths=list(raw.get("paths", [])),
            debug_info=debug_info or {},
            scope=scope,
        )

    def _shape_result(
        self,
        entities: list[Any],
        relations: list[Any],
        paths: list[GraphPath] | None = None,
        debug_info: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> GraphRetrievalResult:
        debug = {"excluded_relations": [], **(debug_info or {})}
        normalized_entities: list[Entity] = []
        for entity in entities:
            parsed = self._coerce_entity(entity)
            if parsed is not None:
                normalized_entities.append(parsed)

        valid_relations: list[Relation] = []
        evidence_chunks_by_id: dict[str, dict[str, Any]] = {}
        for relation in relations:
            parsed_relation = self._coerce_relation(relation)
            if parsed_relation is None:
                debug["excluded_relations"].append({"reason": "invalid_relation", "relation": relation})
                continue
            chunk = self._get_evidence_chunk(parsed_relation.source_chunk_id, scope)
            if not chunk:
                debug["excluded_relations"].append(
                    {"reason": "missing_source_chunk", "source_chunk_id": parsed_relation.source_chunk_id}
                )
                continue
            valid_relations.append(parsed_relation)
            evidence_chunks_by_id[parsed_relation.source_chunk_id] = chunk

        deduped_entities = self._dedupe_entities(normalized_entities)
        deduped_relations = self._dedupe_relations(valid_relations)[: self.relation_limit]
        source_chunk_ids = list(dict.fromkeys(relation.source_chunk_id for relation in deduped_relations if relation.source_chunk_id))
        evidence_chunks = [evidence_chunks_by_id[chunk_id] for chunk_id in source_chunk_ids[: self.evidence_chunk_limit] if chunk_id in evidence_chunks_by_id]
        valid_paths = [path for path in paths or [] if all(relation in deduped_relations for relation in path.relations)]
        return GraphRetrievalResult(
            entities=deduped_entities,
            relations=deduped_relations,
            paths=valid_paths[: self.path_limit],
            source_chunk_ids=source_chunk_ids,
            confidence=self._confidence([relation.confidence for relation in deduped_relations]),
            evidence_chunks=evidence_chunks,
            debug_info=debug,
        )

    def _provider_call(self, method_name: str, *args, scope: KnowledgeBaseScope | None = None, **kwargs):
        method = getattr(self.graph_provider, method_name)
        if "scope" in inspect.signature(method).parameters:
            return method(*args, scope=scope, **kwargs)
        if scope is not None and not scope.compatibility_default:
            raise RuntimeError(f"Graph provider method {method_name} does not support knowledge-base scope")
        return method(*args, **kwargs)

    def _get_evidence_chunk(
        self,
        chunk_id: str,
        scope: KnowledgeBaseScope | None,
    ) -> dict[str, Any] | None:
        method = self.evidence_repository.get_chunk
        if "scope" in inspect.signature(method).parameters:
            return method(chunk_id, scope=scope)
        if scope is not None and not scope.compatibility_default:
            return None
        return method(chunk_id)

    def _coerce_entity(self, raw: Any) -> Entity | None:
        if isinstance(raw, Entity):
            return raw if raw.type in ALLOWED_ENTITY_TYPES else None
        if not isinstance(raw, dict):
            return None
        entity_type = str(raw.get("type") or raw.get("entity_type") or "")
        if entity_type not in ALLOWED_ENTITY_TYPES:
            return None
        return Entity(
            id=str(raw.get("id") or raw.get("entity_id") or ""),
            type=entity_type,
            name=str(raw.get("name") or raw.get("entity_name") or ""),
            description=str(raw.get("description") or ""),
            aliases=list(raw.get("aliases") or []),
            confidence=float(raw.get("confidence", 1.0) or 0.0),
            metadata=dict(raw.get("metadata") or {}),
        )

    def _coerce_relation(self, raw: Any) -> Relation | None:
        if isinstance(raw, Relation):
            return raw if raw.relation_type in ALLOWED_RELATION_TYPES and raw.source_chunk_id else None
        if not isinstance(raw, dict):
            return None
        relation_type = str(raw.get("relation_type") or raw.get("relation") or "")
        if relation_type not in ALLOWED_RELATION_TYPES or not raw.get("source_chunk_id"):
            return None
        try:
            return Relation(
                source_entity_id=str(raw.get("source_entity_id") or raw.get("source") or ""),
                target_entity_id=str(raw.get("target_entity_id") or raw.get("target") or ""),
                relation_type=relation_type,
                description=str(raw.get("description") or ""),
                confidence=float(raw.get("confidence", 1.0) or 0.0),
                source_chunk_id=str(raw.get("source_chunk_id")),
                doc_id=str(raw.get("doc_id") or ""),
                page_start=raw.get("page_start"),
                page_end=raw.get("page_end"),
                extractor_version=str(raw.get("extractor_version") or ""),
                created_at=str(raw.get("created_at") or ""),
                metadata=dict(raw.get("metadata") or {}),
            )
        except ValueError:
            return None

    def _coerce_path(self, raw: Any) -> GraphPath | None:
        if isinstance(raw, GraphPath):
            return raw
        if not isinstance(raw, dict):
            return None
        entities = [entity for entity in (self._coerce_entity(item) for item in raw.get("entities", [])) if entity]
        relations = [relation for relation in (self._coerce_relation(item) for item in raw.get("relations", [])) if relation]
        if not relations:
            return None
        return GraphPath(
            entities=entities,
            relations=relations,
            source_chunk_ids=list(dict.fromkeys(relation.source_chunk_id for relation in relations)),
            confidence=self._confidence([relation.confidence for relation in relations]),
        )

    def _dedupe_scored_entities(self, candidates: list[tuple[Entity, float]]) -> tuple[list[Entity], list[float]]:
        best: dict[str, tuple[Entity, float]] = {}
        for entity, score in candidates:
            key = entity.id or f"{entity.type}:{entity.name}".lower()
            current = best.get(key)
            if current is None or score > current[1]:
                best[key] = (entity, score)
        ordered = sorted(best.values(), key=lambda item: item[1], reverse=True)
        return [item[0] for item in ordered], [item[1] for item in ordered]

    def _dedupe_entities(self, entities: list[Entity]) -> list[Entity]:
        return list({entity.id: entity for entity in entities if entity.id}.values())

    def _dedupe_relations(self, relations: list[Relation]) -> list[Relation]:
        deduped: dict[tuple[str, str, str, str], Relation] = {}
        for relation in relations:
            key = (relation.source_entity_id, relation.target_entity_id, relation.relation_type, relation.source_chunk_id)
            current = deduped.get(key)
            if current is None or relation.confidence > current.confidence:
                deduped[key] = relation
        return list(deduped.values())

    def _confidence(self, scores: list[float]) -> float:
        if not scores:
            return 0.0
        bounded = [max(0.0, min(1.0, float(score))) for score in scores]
        return round(max(bounded), 4)

    def _describe_path(self, path: GraphPath) -> str:
        names_by_id = {entity.id: entity.name for entity in path.entities}
        parts = []
        for relation in path.relations:
            source = names_by_id.get(relation.source_entity_id, relation.source_entity_id)
            target = names_by_id.get(relation.target_entity_id, relation.target_entity_id)
            parts.append(f"{source} -[{relation.relation_type}]-> {target}")
        return " ; ".join(parts)
