import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.models.document_models import Chunk
from app.services.retrieval.citation_verifier import CitationVerifier
from app.services.documents.document_repository import DocumentRepository
from app.services.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService
from app.services.retrieval.rag_service import RAGService


class ScopedVectorStore:
    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self.reset_required = False
        self.hits = []
        self.scopes = []

    def query_dense(self, question, top_k, scope=None):
        self.scopes.append(scope)
        return list(self.hits)

    def query_bm25(self, question, top_k, scope=None):
        self.scopes.append(scope)
        return []

    def count(self):
        return len(self.hits)


class KnowledgeBaseScopedRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repository = DocumentRepository(self.root / "metadata.sqlite3")
        self.knowledge_bases = KnowledgeBaseService(KnowledgeBaseRepository(self.root / "metadata.sqlite3"))
        self.custom = self.knowledge_bases.create("客户资料")
        self.default_scope = self.knowledge_bases.resolve_scope()
        self.custom_scope = self.knowledge_bases.resolve_scope([self.custom.id])
        self.multi_scope = self.knowledge_bases.resolve_scope(["default-knowledge-base", self.custom.id])
        self._write_document("default-doc", "default-child", self.default_scope, "SCOPE_TOKEN default")
        self._write_document("custom-doc", "custom-child", self.custom_scope, "SCOPE_TOKEN custom")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_document(self, doc_id, child_id, scope, content):
        self.repository.upsert_document(
            id=doc_id,
            name="same-name.md",
            file_type="md",
            storage_path=f"uploads/{scope.knowledge_base_id}/same-name.md",
            parse_status="parsed",
            workspace_id=scope.workspace_id,
            knowledge_base_id=scope.knowledge_base_id,
        )
        parent_id = f"{doc_id}-parent"
        metadata = {
            "source": f"{doc_id}.md",
            "workspace_id": scope.workspace_id,
            "knowledge_base_id": scope.knowledge_base_id,
        }
        self.repository.replace_chunks(
            doc_id,
            [
                Chunk(parent_id, doc_id, None, "parent", "", content, content, 1, 1, 2, metadata),
                Chunk(child_id, doc_id, parent_id, "child", "", content, content, 1, 1, 2, metadata),
            ],
            scope=scope,
        )

    def _service(self):
        vector = ScopedVectorStore(self.root / "vectors")
        vector.hits = [
            {
                "content": "",
                "metadata": {
                    "chunk_id": "default-child",
                    "doc_id": "default-doc",
                    "parent_id": "default-doc-parent",
                    "workspace_id": "default-workspace",
                    "knowledge_base_id": "default-knowledge-base",
                },
                "distance": 0.1,
            },
            {
                "content": "",
                "metadata": {
                    "chunk_id": "custom-child",
                    "doc_id": "custom-doc",
                    "parent_id": "custom-doc-parent",
                    "workspace_id": "default-workspace",
                    "knowledge_base_id": self.custom.id,
                },
                "distance": 0.2,
            },
        ]
        service = RAGService(
            vector_store=vector,
            llm_client=SimpleNamespace(),
            chat_model="test",
            system_prompt="test",
            data_dir=str(self.root / "data"),
            top_k=8,
            min_relevance_score=0,
            chunk_size=80,
            chunk_overlap=10,
            document_repository=self.repository,
            knowledge_base_service=self.knowledge_bases,
        )
        return service, vector

    def test_single_and_multi_kb_retrieval_filters_before_fusion_and_preserves_ownership(self):
        service, vector = self._service()

        custom_hits = service.hybrid_retrieve_hits("SCOPE_TOKEN", scope=self.custom_scope)
        multi_hits = service.hybrid_retrieve_hits("SCOPE_TOKEN", scope=self.multi_scope)

        self.assertEqual({"custom-child"}, {item["metadata"]["chunk_id"] for item in custom_hits})
        self.assertEqual(
            {"default-child", "custom-child"}, {item["metadata"]["chunk_id"] for item in multi_hits}
        )
        self.assertTrue(all(scope is self.custom_scope for scope in vector.scopes[: len(vector.scopes) // 2]))
        self.assertEqual(
            {"default-knowledge-base", self.custom.id},
            {item["metadata"]["knowledge_base_id"] for item in multi_hits},
        )

    def test_parent_lookup_and_citation_verifier_block_cross_kb_chunks(self):
        service, _ = self._service()
        malicious_hit = {
            "content": "default evidence",
            "metadata": {
                "chunk_id": "default-child",
                "parent_id": "default-doc-parent",
                "workspace_id": "default-workspace",
                "knowledge_base_id": "default-knowledge-base",
            },
            "hybrid_score": 0.9,
        }

        parents = service.recall_parent_hits([malicious_hit], scope=self.custom_scope)
        verification = CitationVerifier(self.repository).verify(
            citations=[{"chunk_id": "default-child"}],
            used_chunks=["custom-child"],
            graph_paths=[{"relations": [{"source_chunk_id": "default-child"}]}],
            scope=self.custom_scope,
        )

        self.assertEqual([], parents)
        self.assertFalse(verification.valid)
        self.assertEqual(["default-child"], verification.invalid_citations)
        self.assertEqual(["default-child"], verification.invalid_graph_source_chunks)
        self.assertEqual(["custom-child"], verification.verified_chunks)

    def test_default_compatibility_is_one_kb_and_fts_is_scoped(self):
        service, vector = self._service()
        vector.hits = []

        scope = service.resolve_scope()
        keyword_hits = service.keyword_retrieve_hits("SCOPE_TOKEN", scope=scope)

        self.assertTrue(scope.compatibility_default)
        self.assertEqual(("default-knowledge-base",), scope.selected_knowledge_base_ids)
        self.assertEqual(["default-child"], [item["metadata"]["chunk_id"] for item in keyword_hits])

    def test_document_id_scope_filters_dense_hydration_keyword_and_parent_recall(self):
        service, vector = self._service()
        service.direct_load_max_chunks = 0
        doc_scope = self.knowledge_bases.resolve_scope(["default-knowledge-base"], document_ids=["default-doc"])

        dense_hits = service.hybrid_retrieve_hits("SCOPE_TOKEN", scope=doc_scope)
        keyword_hits = service.keyword_retrieve_hits("SCOPE_TOKEN", scope=doc_scope)
        malicious_parent = service.recall_parent_hits(
            [
                {
                    "content": "custom evidence",
                    "metadata": {
                        "chunk_id": "custom-child",
                        "doc_id": "custom-doc",
                        "parent_id": "custom-doc-parent",
                        "workspace_id": "default-workspace",
                        "knowledge_base_id": self.custom.id,
                    },
                    "hybrid_score": 0.9,
                }
            ],
            scope=doc_scope,
        )

        self.assertEqual(["default-child"], [item["metadata"]["chunk_id"] for item in dense_hits])
        self.assertEqual(["default-child"], [item["metadata"]["chunk_id"] for item in keyword_hits])
        self.assertEqual([], malicious_parent)
        self.assertEqual(("default-doc",), vector.scopes[0].document_ids)

    def test_two_kb_query_smoke_and_archive_isolation(self):
        service, vector = self._service()
        vector.hits = []
        service.stream_answer = lambda question, hits=None, **kwargs: iter(["scoped answer"])

        default_result = service.answer_query("SCOPE_TOKEN", scope=self.default_scope)
        custom_result = service.answer_query("SCOPE_TOKEN", scope=self.custom_scope)
        multi_result = service.answer_query("SCOPE_TOKEN", scope=self.multi_scope)
        self.knowledge_bases.archive(self.custom.id)

        self.assertEqual({"default-doc"}, {item["doc_id"] for item in default_result["citations"]})
        self.assertEqual({"custom-doc"}, {item["doc_id"] for item in custom_result["citations"]})
        self.assertEqual(
            {"default-doc", "custom-doc"}, {item["doc_id"] for item in multi_result["citations"]}
        )
        with self.assertRaises(KeyError):
            self.knowledge_bases.resolve_scope([self.custom.id])
        remaining = service.answer_query("SCOPE_TOKEN", scope=self.default_scope)
        self.assertEqual({"default-doc"}, {item["doc_id"] for item in remaining["citations"]})

    def test_feedback_document_is_written_and_indexed_inside_explicit_kb(self):
        service = object.__new__(RAGService)
        service.default_scope = self.default_scope
        service.knowledge_base_service = None
        service.audit_repository = SimpleNamespace(create_feedback=lambda *args, **kwargs: None)
        service.feedback_dir = self.root / "data" / "feedback"
        service._generate_qa_title = lambda question, answer: "纠错记录"
        indexed = []

        def capture_index(file_path, scope):
            indexed.append((Path(file_path), scope, Path(file_path).read_text(encoding="utf-8")))
            return {"source": str(file_path), "indexed_chunks": 1}

        service.parse_and_index_document = capture_index

        result = service.create_feedback_document("问题", "标准答案", scope=self.custom_scope)

        self.assertEqual(1, result["chunks"])
        self.assertEqual(self.custom.id, indexed[0][0].parent.name)
        self.assertIs(self.custom_scope, indexed[0][1])
        self.assertIn(f"knowledge_base_id: {self.custom.id}", indexed[0][2])
        self.assertNotIn("knowledge_base_id: default-knowledge-base", indexed[0][2])


if __name__ == "__main__":
    unittest.main()
