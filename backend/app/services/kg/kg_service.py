import logging
from dataclasses import replace

from app.models.document_models import Chunk
from app.models.kg_models import Entity, EntityMention, Relation, generated_id
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.kg.entity_resolver import BaselineEntityResolver, EntityResolverProvider, EntityVectorProvider
from app.services.kg.graph_store import GraphStoreProvider
from app.services.kg.kg_extractor import KGExtractorProvider
from app.services.kg.kg_repository import KGRepository

logger = logging.getLogger(__name__)


class KGEnrichmentService:
    def __init__(
        self,
        repository: KGRepository,
        extractor: KGExtractorProvider,
        resolver: EntityResolverProvider | None = None,
        entity_vector_provider: EntityVectorProvider | None = None,
        graph_store: GraphStoreProvider | None = None,
    ):
        self.repository = repository
        self.extractor = extractor
        self.entity_vector_provider = entity_vector_provider
        self.graph_store = graph_store
        self.resolver = resolver or BaselineEntityResolver(entity_vector_provider=entity_vector_provider)

    def enrich_document(
        self,
        doc_id: str,
        chunks: list[Chunk],
        scope: KnowledgeBaseScope | None = None,
    ) -> dict:
        scope = scope or self._scope_from_chunks(chunks)
        parent_chunks = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
        task = self.repository.create_extraction_task(
            doc_id,
            extractor_version=self.extractor.extractor_version,
            parent_chunk_count=len(parent_chunks),
            scope=scope,
        )
        task_id = task["id"]
        self.repository.mark_task_started(task_id)
        errors: list[str] = []
        mentions: list[EntityMention] = []
        canonical_by_name: dict[str, Entity] = {}
        relation_buffer: list[Relation] = []

        for chunk in parent_chunks:
            try:
                result = self.extractor.extract(
                    doc_id=chunk.doc_id,
                    parent_id=chunk.id,
                    chunk_id=chunk.id,
                    title_path=chunk.title_path,
                    content=chunk.content_markdown or chunk.content,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
                local_name_to_entity: dict[str, Entity] = {}
                for entity in result.entities:
                    scoped_entity = replace(
                        entity,
                        metadata={
                            **entity.metadata,
                            "workspace_id": scope.workspace_id,
                            "knowledge_base_id": scope.knowledge_base_id,
                        },
                    )
                    canonical = self.resolver.resolve(scoped_entity)
                    canonical = replace(
                        canonical,
                        metadata={
                            **canonical.metadata,
                            "workspace_id": scope.workspace_id,
                            "knowledge_base_id": scope.knowledge_base_id,
                        },
                    )
                    canonical_by_name[entity.name] = canonical
                    canonical_by_name[canonical.name] = canonical
                    for alias in canonical.aliases:
                        canonical_by_name[alias] = canonical
                    local_name_to_entity[entity.name] = canonical
                    mentions.append(self._mention_for_entity(canonical, chunk, entity.name))
                for relation in result.relations:
                    source = local_name_to_entity.get(relation.source_entity_id) or canonical_by_name.get(relation.source_entity_id)
                    target = local_name_to_entity.get(relation.target_entity_id) or canonical_by_name.get(relation.target_entity_id)
                    if source is None or target is None:
                        errors.append(f"Unresolved relation endpoint: {relation.source_entity_id}->{relation.target_entity_id}")
                        continue
                    relation_buffer.append(
                        Relation(
                            source_entity_id=source.id,
                            target_entity_id=target.id,
                            relation_type=relation.relation_type,
                            description=relation.description,
                            confidence=relation.confidence,
                            source_chunk_id=relation.source_chunk_id,
                            doc_id=relation.doc_id,
                            page_start=relation.page_start,
                            page_end=relation.page_end,
                            extractor_version=relation.extractor_version,
                            created_at=relation.created_at,
                            metadata={
                                **relation.metadata,
                                "workspace_id": scope.workspace_id,
                                "knowledge_base_id": scope.knowledge_base_id,
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("KG extraction failed for chunk %s: %s", chunk.id, exc)
                errors.append(str(exc))

        if mentions:
            self.repository.insert_entity_mentions(mentions)
        entities = list({entity.id: entity for entity in canonical_by_name.values()}.values())
        try:
            if self.entity_vector_provider and entities:
                self.entity_vector_provider.upsert_entities(entities)
            if self.graph_store:
                for entity in entities:
                    self.graph_store.upsert_entity(entity)
                for relation in relation_buffer:
                    self.graph_store.upsert_relation(relation)
        except Exception as exc:
            logger.warning("KG graph/vector write failed for doc %s: %s", doc_id, exc)
            errors.append(str(exc))

        if errors and mentions:
            self.repository.mark_task_partial_failed(task_id, "; ".join(errors))
        elif errors:
            self.repository.mark_task_failed(task_id, "; ".join(errors))
        else:
            self.repository.mark_task_completed(task_id)
        return self.repository.get_task(task_id) or {}

    def _mention_for_entity(self, canonical: Entity, chunk: Chunk, mention_text: str) -> EntityMention:
        return EntityMention(
            id=f"mention-{generated_id(canonical.id, chunk.id, mention_text)}",
            entity_id=canonical.id,
            entity_type=canonical.type,
            entity_name=canonical.name,
            doc_id=chunk.doc_id,
            chunk_id=chunk.id,
            parent_id=chunk.parent_id or chunk.id,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            mention_text=mention_text,
            confidence=canonical.confidence,
            aliases=canonical.aliases,
            description=canonical.description,
            metadata=canonical.metadata,
        )

    def _scope_from_chunks(self, chunks: list[Chunk]) -> KnowledgeBaseScope:
        if not chunks:
            return KnowledgeBaseScope("default-workspace", ("default-knowledge-base",), compatibility_default=True)
        workspace_ids = {str(chunk.metadata.get("workspace_id", "default-workspace")) for chunk in chunks}
        knowledge_base_ids = {
            str(chunk.metadata.get("knowledge_base_id", "default-knowledge-base")) for chunk in chunks
        }
        if len(workspace_ids) != 1 or len(knowledge_base_ids) != 1:
            raise ValueError("KG enrichment chunks must share one knowledge base scope")
        return KnowledgeBaseScope(next(iter(workspace_ids)), (next(iter(knowledge_base_ids)),))
