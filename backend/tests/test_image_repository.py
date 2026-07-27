import tempfile
import unittest
from pathlib import Path

from app.models.document_models import ParsedImage
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseScope
from app.services.document_repository import DocumentRepository
from app.services.image_repository import ImageRepository
from app.services.knowledge_base_repository import KnowledgeBaseRepository


class ImageRepositoryTests(unittest.TestCase):
    def test_scoped_image_and_operation_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            scope = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            docs = DocumentRepository(path)
            docs.upsert_document("doc-1", "scan.pdf", "pdf", "scan.pdf", "parsed")
            repository = ImageRepository(path)
            image = ParsedImage("img-1", "media/img.jpg", "scanned_pdf", page_number=2)
            stored = repository.add_image("doc-1", image, scope)
            self.assertEqual("media/img.jpg", stored["storage_key"])
            self.assertEqual("local", stored["storage_provider"])
            operation = repository.create_operation("img-1", "doc-1", "ocr", scope)
            started = repository.update_operation(operation["id"], scope, status="processing", increment_attempt=True)
            completed = repository.update_operation(
                operation["id"], scope, status="completed", provider_ref="fake", result_chunk_id="chunk-1"
            )
            self.assertEqual(1, started["attempt"])
            self.assertEqual("completed", completed["status"])
            self.assertEqual(1, completed["attempt"])
            self.assertEqual(1, len(repository.list_images("doc-1", scope)))
            self.assertEqual(1, len(repository.list_operations("doc-1", scope, status="completed")))
            self.assertEqual(["media/img.jpg"], repository.delete_document_images("doc-1", scope))
            with self.assertRaises(FileNotFoundError):
                repository.get_image("img-1", scope)

    def test_cross_kb_lookup_does_not_reveal_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            scope = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            KnowledgeBaseRepository(path).create_knowledge_base(
                KnowledgeBase(id="other-kb", workspace_id="default-workspace", name="Other")
            )
            docs = DocumentRepository(path)
            docs.upsert_document("doc-1", "scan.pdf", "pdf", "scan.pdf", "parsed")
            docs.upsert_document(
                "doc-2",
                "scan.pdf",
                "pdf",
                "scan.pdf",
                "parsed",
                workspace_id="default-workspace",
                knowledge_base_id="other-kb",
            )
            repository = ImageRepository(path)
            repository.add_image("doc-1", ParsedImage("img-1", "media/img.jpg", "scanned_pdf"), scope)
            other = KnowledgeBaseScope("default-workspace", ("other-kb",))
            with self.assertRaises(FileNotFoundError):
                repository.get_image("img-1", other)
            with self.assertRaises(FileNotFoundError):
                repository.create_operation("img-1", "doc-2", "ocr", other)

    def test_cancel_and_cleanup_abandoned_staged_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            scope = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            DocumentRepository(path).upsert_document("doc-1", "scan.pdf", "pdf", "scan.pdf", "parsed")
            repository = ImageRepository(path)
            repository.add_image("doc-1", ParsedImage("img-1", "media/one.jpg", "scanned_pdf"), scope)
            repository.add_image("doc-1", ParsedImage("img-2", "media/two.jpg", "embedded_image"), scope)
            repository.create_operation("img-1", "doc-1", "ocr", scope)
            op_2 = repository.create_operation("img-2", "doc-1", "caption", scope)
            repository.update_operation(op_2["id"], scope, status="processing", increment_attempt=True)

            self.assertEqual(2, repository.cancel_document_operations("doc-1", scope))
            self.assertEqual(["media/one.jpg", "media/two.jpg"], repository.cleanup_abandoned_staged_resources("doc-1", scope))
            self.assertEqual([], repository.list_images("doc-1", scope))
            self.assertEqual([], repository.list_operations("doc-1", scope))

    def test_document_deletion_cascades_images_and_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            scope = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            docs = DocumentRepository(path)
            docs.upsert_document("doc-1", "scan.pdf", "pdf", "scan.pdf", "parsed")
            repository = ImageRepository(path)
            repository.add_image("doc-1", ParsedImage("img-1", "media/img.jpg", "scanned_pdf"), scope)
            repository.create_operation("img-1", "doc-1", "ocr", scope)

            docs.delete_document("doc-1", scope)

            with self.assertRaises(FileNotFoundError):
                repository.get_image("img-1", scope)
            self.assertEqual([], repository.list_operations("doc-1", scope))

    def test_partial_failure_retry_and_missing_resource_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            scope = KnowledgeBaseScope("default-workspace", ("default-knowledge-base",))
            DocumentRepository(path).upsert_document("doc-1", "scan.pdf", "pdf", "scan.pdf", "parsed")
            repository = ImageRepository(path)
            repository.add_image("doc-1", ParsedImage("img-1", "media/one.jpg", "scanned_pdf"), scope)
            repository.add_image("doc-1", ParsedImage("img-2", "media/two.jpg", "scanned_pdf"), scope)
            failed = repository.create_operation("img-1", "doc-1", "ocr", scope)
            completed = repository.create_operation("img-2", "doc-1", "ocr", scope)
            repository.update_operation(failed["id"], scope, status="failed", error_message="provider said no")
            repository.update_operation(completed["id"], scope, status="completed", result_chunk_id="chunk-2")

            self.assertEqual(1, len(repository.list_operations("doc-1", scope, status="failed")))
            retried = repository.retry_operation(failed["id"], scope)
            self.assertEqual("pending", retried["status"])
            self.assertEqual(1, retried["attempt"])
            with self.assertRaises(ValueError):
                repository.retry_operation(completed["id"], scope)
            with self.assertRaises(FileNotFoundError):
                repository.create_operation("missing-image", "doc-1", "caption", scope)
            with self.assertRaises(FileNotFoundError):
                repository.delete_image("missing-image", scope)


if __name__ == "__main__":
    unittest.main()
