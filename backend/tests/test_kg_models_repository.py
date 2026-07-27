import tempfile
import unittest
from pathlib import Path

from app.models.document_models import Chunk
from app.models.kg_models import Entity, EntityMention, GraphPath, Relation
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.document_repository import DocumentRepository
from app.services.kg_repository import KGRepository
from app.services.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge_base_service import KnowledgeBaseService


class KGModelsRepositoryTests(unittest.TestCase):
    def test_relation_requires_traceable_evidence_fields(self):
        relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            description="Service A depends on Redis",
            confidence=0.91,
            source_chunk_id="parent-1",
            doc_id="doc-1",
            page_start=3,
            extractor_version="kg-v1",
            created_at="2026-07-06T12:00:00",
        )

        self.assertEqual("parent-1", relation.source_chunk_id)
        self.assertEqual("doc-1", relation.doc_id)
        self.assertEqual("DEPENDS_ON", relation.relation_type)

    def test_models_reject_unknown_entity_and_relation_types(self):
        with self.assertRaises(ValueError):
            Entity(id="e1", type="UnknownThing", name="X")

        with self.assertRaises(ValueError):
            Relation(
                source_entity_id="e1",
                target_entity_id="e2",
                relation_type="MAGICALLY_LINKS",
                source_chunk_id="c1",
                doc_id="doc-1",
                extractor_version="kg-v1",
            )

    def test_graph_path_collects_entities_relations_and_source_chunks(self):
        entity = Entity(id="entity-redis", type="Middleware", name="Redis")
        relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            source_chunk_id="parent-1",
            doc_id="doc-1",
            extractor_version="kg-v1",
        )
        path = GraphPath(entities=[entity], relations=[relation], source_chunk_ids=["parent-1"], confidence=0.8)

        self.assertEqual(["parent-1"], path.source_chunk_ids)
        self.assertEqual(0.8, path.confidence)

    def test_repository_tracks_tasks_mentions_and_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kg.sqlite3"
            documents = DocumentRepository(path)
            self._seed_document(documents, "doc-1", "parent-1")
            repo = KGRepository(path)
            task = repo.create_extraction_task("doc-1", extractor_version="kg-v1", parent_chunk_count=2)
            repo.mark_task_started(task["id"])
            repo.mark_task_partial_failed(task["id"], "one parent chunk failed")
            repo.mark_task_failed(task["id"], "neo4j unavailable")
            repo.upsert_community_summary("community-1", "summary", ["entity-1"], ["chunk-1"], 0.7)
            mention = EntityMention(
                id="mention-1",
                entity_id="entity-redis",
                entity_type="Middleware",
                entity_name="Redis",
                doc_id="doc-1",
                chunk_id="parent-1",
                parent_id="parent-1",
                page_start=1,
                page_end=2,
                mention_text="Redis",
                confidence=0.9,
                created_at="2026-07-06T12:00:00",
            )
            repo.insert_entity_mentions([mention])

            tasks = repo.list_extraction_tasks("doc-1")
            mentions_by_doc = repo.list_entity_mentions(doc_id="doc-1")
            mentions_by_entity = repo.list_entity_mentions(entity_id="entity-redis")
            summaries = repo.list_community_summaries()

        self.assertEqual("failed", tasks[0]["status"])
        self.assertEqual("neo4j unavailable", tasks[0]["error_message"])
        self.assertEqual("Redis", mentions_by_doc[0]["mention_text"])
        self.assertEqual("mention-1", mentions_by_entity[0]["id"])
        self.assertEqual("community-1", summaries[0]["community_id"])

    def test_repository_isolates_tasks_mentions_and_same_named_communities_by_kb(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kg.sqlite3"
            documents = DocumentRepository(path)
            knowledge_bases = KnowledgeBaseService(KnowledgeBaseRepository(path))
            kb_b = knowledge_bases.create("KB B")
            scope_a = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            scope_b = KnowledgeBaseScope("default-workspace", (kb_b.id,))
            self._seed_document(documents, "doc-a", "chunk-a", scope_a)
            self._seed_document(documents, "doc-b", "chunk-b", scope_b)
            repo = KGRepository(path)
            repo.create_extraction_task("doc-a", "kg-v1", scope=scope_a)
            repo.create_extraction_task("doc-b", "kg-v1", scope=scope_b)
            repo.upsert_community_summary("shared", "summary-a", ["a"], ["chunk-a"], 0.9, scope=scope_a)
            repo.upsert_community_summary("shared", "summary-b", ["b"], ["chunk-b"], 0.8, scope=scope_b)
            mentions = [
                EntityMention(
                    id=f"mention-{suffix}",
                    entity_id=f"entity-{suffix}",
                    entity_type="Concept",
                    entity_name=f"Entity {suffix}",
                    doc_id=f"doc-{suffix}",
                    chunk_id=f"chunk-{suffix}",
                    parent_id=f"chunk-{suffix}",
                    page_start=1,
                    page_end=1,
                    mention_text=f"Entity {suffix}",
                    confidence=0.9,
                    metadata={"workspace_id": "default-workspace", "knowledge_base_id": kb_id},
                )
                for suffix, kb_id in (("a", "default-knowledge-base"), ("b", kb_b.id))
            ]
            repo.insert_entity_mentions(mentions)

            tasks_a = repo.list_extraction_tasks(scope=scope_a)
            mentions_a = repo.list_entity_mentions(scope=scope_a)
            summaries_a = repo.list_community_summaries(scope=scope_a)
            summaries_b = repo.list_community_summaries(scope=scope_b)

        self.assertEqual(["doc-a"], [item["doc_id"] for item in tasks_a])
        self.assertEqual(["chunk-a"], [item["chunk_id"] for item in mentions_a])
        self.assertEqual(["summary-a"], [item["summary"] for item in summaries_a])
        self.assertEqual(["summary-b"], [item["summary"] for item in summaries_b])

    def _seed_document(
        self,
        repository: DocumentRepository,
        doc_id: str,
        chunk_id: str,
        scope: KnowledgeBaseScope | None = None,
    ) -> None:
        scope = scope or repository.default_scope()
        repository.upsert_document(
            doc_id,
            f"{doc_id}.md",
            "md",
            f"{doc_id}.md",
            "parsed",
            workspace_id=scope.workspace_id,
            knowledge_base_id=scope.knowledge_base_id,
        )
        repository.replace_chunks(
            doc_id,
            [
                Chunk(
                    chunk_id,
                    doc_id,
                    None,
                    "parent",
                    "",
                    "content",
                    "content",
                    1,
                    1,
                    1,
                    {"workspace_id": scope.workspace_id, "knowledge_base_id": scope.knowledge_base_id},
                )
            ],
            scope,
        )


if __name__ == "__main__":
    unittest.main()
