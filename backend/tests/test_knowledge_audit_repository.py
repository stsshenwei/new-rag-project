import tempfile
import unittest
from pathlib import Path

from app.services.knowledge.audit_repository import KnowledgeAuditRepository
from app.services.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService


class KnowledgeAuditRepositoryTests(unittest.TestCase):
    def test_queries_and_feedback_are_isolated_by_knowledge_base_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases = KnowledgeBaseService(KnowledgeBaseRepository(path))
            kb_b = knowledge_bases.create("KB B")
            scope_a = knowledge_bases.resolve_scope()
            scope_b = knowledge_bases.resolve_scope([kb_b.id])
            multi_scope = knowledge_bases.resolve_scope([scope_a.knowledge_base_id, kb_b.id])
            repository = KnowledgeAuditRepository(path)

            query_a = repository.start_query("question a", scope_a, "fact")
            repository.finish_query(
                query_a,
                status="completed",
                tool_calls=[{"tool": "RawRAGTool"}],
                citation_chunk_ids=["chunk-a"],
            )
            query_multi = repository.start_query("question multi", multi_scope, "comparison")
            repository.finish_query(query_multi, status="completed")
            feedback = repository.create_feedback(
                scope_a,
                query_log_id=query_a,
                correction="corrected answer",
                source_chunk_ids=["chunk-a"],
            )

            self.assertEqual([query_a], [item["id"] for item in repository.list_queries(scope_a)])
            self.assertEqual(
                {query_a, query_multi},
                {item["id"] for item in repository.list_queries(multi_scope)},
            )
            self.assertEqual("default-knowledge-base", feedback["knowledge_base_id"])
            self.assertEqual([], repository.list_feedback(scope_b))
            with self.assertRaises(ValueError):
                repository.create_feedback(
                    scope_b,
                    query_log_id=query_a,
                    correction="cross-scope correction",
                )


if __name__ == "__main__":
    unittest.main()
