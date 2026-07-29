import tempfile
import unittest
from pathlib import Path

from app.models.document_models import Chunk
from app.models.processing_config import PROCESSING_VERSION
from app.services.documents.document_repository import DocumentRepository
from app.services.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService
from app.services.documents.upload_batch_repository import UploadBatchRepository


class DocumentRepositoryTests(unittest.TestCase):
    def _document(self, repo, doc_id="doc-1", knowledge_base_id=None, workspace_id=None):
        repo.upsert_document(
            id=doc_id,
            name=f"{doc_id}.pdf",
            file_type="pdf",
            storage_path=f"uploads/{doc_id}.pdf",
            parse_status="parsed",
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
        )

    def _chunk(self, chunk_id, chunk_type="child", content="ERR_CODE_42 use --timeout 30", parent_id="parent-1"):
        return Chunk(
            id=chunk_id,
            doc_id="doc-1",
            parent_id=parent_id,
            chunk_type=chunk_type,
            title_path="CLI/Errors",
            content=content,
            content_markdown=content,
            page_start=7,
            page_end=8,
            token_count=8,
            metadata={"source": "manual.md"},
        )

    def test_repository_saves_document_and_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            repo.upsert_document(
                id="doc-1",
                name="manual.pdf",
                file_type="pdf",
                storage_path="uploads/manual.pdf",
                parse_status="parsed",
                metadata_json={"page_count": 2},
            )
            repo.replace_chunks(
                "doc-1",
                [
                    Chunk(
                        id="parent-1",
                        doc_id="doc-1",
                        parent_id=None,
                        chunk_type="parent",
                        title_path="章",
                        content="完整上下文",
                        content_markdown="完整上下文",
                        page_start=1,
                        page_end=1,
                        token_count=10,
                        metadata={},
                    )
                ],
            )

            docs = repo.list_documents()
            self.assertEqual("doc-1", docs[0]["id"])
            self.assertEqual("parsed", docs[0]["parse_status"])
            self.assertEqual("完整上下文", repo.get_chunk("parent-1")["content"])


    def test_repository_round_trips_enriched_chunk_metadata(self):
        metadata = {
            "caption": "Table 1: Options",
            "rows": [{"Name": "timeout", "Value": "30"}],
            "layout": {"bbox": [1, 2, 3, 4]},
            "ocr": {"provider": "docling", "confidence": 0.91},
            "scores": {"vector": 0.8, "bm25": 2.1},
        }
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            self._document(repo)
            repo.replace_chunks(
                "doc-1",
                [
                    Chunk(
                        id="table-1",
                        doc_id="doc-1",
                        parent_id="parent-1",
                        chunk_type="table",
                        title_path="Manual/Options",
                        content="timeout 30",
                        content_markdown="| Name | Value |",
                        page_start=2,
                        page_end=3,
                        token_count=5,
                        metadata=metadata,
                    )
                ],
            )

            chunk = repo.get_chunk("table-1")

        for key, value in metadata.items():
            self.assertEqual(value, chunk["metadata_json"][key])
        self.assertEqual(PROCESSING_VERSION, chunk["metadata_json"]["processing_version"])

    def test_repository_adds_default_chunk_provenance_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            self._document(repo)
            repo.replace_chunks("doc-1", [self._chunk("child-1")])

            chunk = repo.get_chunk("child-1")

        self.assertEqual(PROCESSING_VERSION, chunk["metadata_json"]["processing_version"])
        self.assertEqual("chars", chunk["metadata_json"]["size_unit"])
        self.assertEqual("legacy", chunk["metadata_json"]["strategy"])

    def test_fts5_indexes_child_table_ocr_and_image_chunks_but_not_parent_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            self._document(repo)
            repo.replace_chunks(
                "doc-1",
                [
                    self._chunk("parent-1", chunk_type="parent", content="ERR_CODE_42 parent text", parent_id=None),
                    self._chunk("child-1", chunk_type="child", content="ERR_CODE_42 child text"),
                    self._chunk("table-1", chunk_type="table", content="API_NAME table text"),
                    self._chunk("ocr-1", chunk_type="ocr", content="CONFIG_KEY ocr text"),
                    self._chunk("image-ocr-1", chunk_type="image_ocr", content="IMAGE_TOKEN ocr text"),
                    self._chunk("caption-1", chunk_type="image_caption", content="CAPTION_TOKEN caption text"),
                ],
            )

            error_hits = repo.search_keyword_chunks("ERR_CODE_42", top_k=10)
            api_hits = repo.search_keyword_chunks("API_NAME", top_k=10)
            config_hits = repo.search_keyword_chunks("CONFIG_KEY", top_k=10)
            image_hits = repo.search_keyword_chunks("IMAGE_TOKEN", top_k=10)
            caption_hits = repo.search_keyword_chunks("CAPTION_TOKEN", top_k=10)
            repo.rebuild_keyword_index()
            rebuilt_image_hits = repo.search_keyword_chunks("IMAGE_TOKEN", top_k=10)

        self.assertEqual(["child-1"], [hit["id"] for hit in error_hits])
        self.assertEqual(["table-1"], [hit["id"] for hit in api_hits])
        self.assertEqual(["ocr-1"], [hit["id"] for hit in config_hits])
        self.assertEqual(["image-ocr-1"], [hit["id"] for hit in image_hits])
        self.assertEqual(["caption-1"], [hit["id"] for hit in caption_hits])
        self.assertEqual(["image-ocr-1"], [hit["id"] for hit in rebuilt_image_hits])
        self.assertGreater(error_hits[0]["keyword_score"], 0)
        self.assertEqual("doc-1", error_hits[0]["doc_id"])
        self.assertEqual("parent-1", error_hits[0]["parent_id"])

    def test_fts5_replace_delete_reset_and_rebuild_stay_in_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            self._document(repo)
            repo.replace_chunks("doc-1", [self._chunk("child-1", content="OLD_TOKEN")])
            self.assertEqual(["child-1"], [hit["id"] for hit in repo.search_keyword_chunks("OLD_TOKEN", top_k=10)])

            repo.replace_chunks("doc-1", [self._chunk("child-2", content="NEW_TOKEN")])
            self.assertEqual([], repo.search_keyword_chunks("OLD_TOKEN", top_k=10))
            self.assertEqual(["child-2"], [hit["id"] for hit in repo.search_keyword_chunks("NEW_TOKEN", top_k=10)])

            repo.delete_document("doc-1")
            self.assertEqual([], repo.search_keyword_chunks("NEW_TOKEN", top_k=10))

            self._document(repo)
            repo.replace_chunks("doc-1", [self._chunk("child-3", content="REBUILD_TOKEN")])
            repo.rebuild_keyword_index()
            self.assertEqual(["child-3"], [hit["id"] for hit in repo.search_keyword_chunks("REBUILD_TOKEN", top_k=10)])

            repo.reset()
            self.assertEqual([], repo.search_keyword_chunks("REBUILD_TOKEN", top_k=10))

    def test_delete_document_unlinks_upload_file_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag.sqlite3"
            repo = DocumentRepository(path)
            uploads = UploadBatchRepository(path)
            scope = repo.default_scope()
            self._document(repo)
            batch = uploads.create_batch(scope)
            file_task = uploads.add_file(
                batch["id"],
                scope,
                original_name="doc-1.pdf",
                relative_path="doc-1.pdf",
                storage_path="uploads/doc-1.pdf",
                size=123,
            )
            uploads.update_file(file_task["id"], scope, status="completed", document_id="doc-1", chunks=1)

            repo.delete_document("doc-1", scope)

            updated_batch = uploads.get_batch(batch["id"], scope)
            self.assertIsNone(updated_batch["files"][0]["document_id"])
            self.assertEqual([], repo.list_documents(scope))

    def test_fts_and_rebuild_are_isolated_across_knowledge_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag.sqlite3"
            repo = DocumentRepository(path)
            knowledge_bases = KnowledgeBaseService(KnowledgeBaseRepository(path))
            custom = knowledge_bases.create("第二知识库")
            custom_scope = knowledge_bases.resolve_scope([custom.id])
            multi_scope = knowledge_bases.resolve_scope(["default-knowledge-base", custom.id])
            self._document(repo, doc_id="doc-1")
            repo.upsert_document(
                id="doc-2",
                name="doc-1.pdf",
                file_type="pdf",
                storage_path="uploads/doc-1.pdf",
                parse_status="parsed",
                workspace_id=custom.workspace_id,
                knowledge_base_id=custom.id,
            )
            repo.replace_chunks("doc-1", [self._chunk("default-child", content="SHARED_TOKEN")])
            repo.replace_chunks(
                "doc-2",
                [
                    Chunk(
                        id="custom-child",
                        doc_id="doc-2",
                        parent_id="custom-parent",
                        chunk_type="child",
                        title_path="CLI/Errors",
                        content="SHARED_TOKEN",
                        content_markdown="SHARED_TOKEN",
                        page_start=1,
                        page_end=1,
                        token_count=2,
                        metadata={"workspace_id": custom.workspace_id, "knowledge_base_id": custom.id},
                    )
                ],
                scope=custom_scope,
            )

            default_hits = repo.search_keyword_chunks("SHARED_TOKEN", scope=repo.default_scope())
            custom_hits = repo.search_keyword_chunks("SHARED_TOKEN", scope=custom_scope)
            multi_hits = repo.search_keyword_chunks("SHARED_TOKEN", scope=multi_scope)
            repo.reset(repo.default_scope())

            self.assertEqual(["default-child"], [item["id"] for item in default_hits])
            self.assertEqual(["custom-child"], [item["id"] for item in custom_hits])
            self.assertEqual({"default-child", "custom-child"}, {item["id"] for item in multi_hits})
            self.assertEqual([], repo.list_documents(repo.default_scope()))
            self.assertEqual(["doc-2"], [item["id"] for item in repo.list_documents(custom_scope)])


if __name__ == "__main__":
    unittest.main()
