import tempfile
import unittest
from pathlib import Path

from app.services.documents.document_repository import DocumentRepository
from app.services.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService
from app.services.documents.upload_batch_repository import UploadBatchRepository


class UploadBatchRepositoryTests(unittest.TestCase):
    def _services(self, path: Path):
        documents = DocumentRepository(path)
        knowledge_bases = KnowledgeBaseService(KnowledgeBaseRepository(path))
        uploads = UploadBatchRepository(path)
        return knowledge_bases, uploads, documents

    def test_create_batch_add_file_update_statuses_and_fetch_by_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases, uploads, documents = self._services(path)
            scope = knowledge_bases.resolve_scope()

            batch = uploads.create_batch(scope, {"chunk_size": 800, "dense_enabled": True})
            file_task = uploads.add_file(
                batch["id"],
                scope,
                original_name="manual.md",
                relative_path="docs/manual.md",
                storage_path="uploads/docs/manual.md",
                size=123,
            )
            documents.upsert_document(
                id="doc-1",
                name="manual.md",
                file_type="md",
                storage_path="uploads/docs/manual.md",
                parse_status="parsed",
                workspace_id=scope.workspace_id,
                knowledge_base_id=scope.knowledge_base_id,
            )
            uploads.update_file(
                file_task["id"],
                scope,
                status="completed",
                document_id="doc-1",
                chunks=3,
            )
            completed = uploads.update_batch(batch["id"], scope, status="completed")

            self.assertEqual("completed", completed["status"])
            self.assertIsNotNone(completed["completed_at"])
            self.assertEqual({"chunk_size": 800, "dense_enabled": True}, completed["settings"])
            self.assertEqual(1, completed["aggregate"]["completed"])
            self.assertEqual("doc-1", completed["files"][0]["document_id"])
            self.assertEqual(3, completed["files"][0]["chunks"])
            self.assertEqual([completed["id"]], [item["id"] for item in uploads.list_batches(scope)])

    def test_rejects_cross_knowledge_base_batch_access_without_leaking_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases, uploads, _documents = self._services(path)
            default_scope = knowledge_bases.resolve_scope()
            other = knowledge_bases.create("Other KB")
            other_scope = knowledge_bases.resolve_scope([other.id])

            batch = uploads.create_batch(default_scope)
            uploads.add_file(
                batch["id"],
                default_scope,
                original_name="secret.md",
                relative_path="secret.md",
                storage_path="uploads/secret.md",
                size=10,
            )

            with self.assertRaises(KeyError):
                uploads.get_batch(batch["id"], other_scope)
            self.assertEqual([], uploads.list_batches(other_scope))

    def test_archived_knowledge_base_cannot_create_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases, uploads, _documents = self._services(path)
            archived = knowledge_bases.create("Archive me")
            archived_scope = knowledge_bases.resolve_scope([archived.id])
            knowledge_bases.archive(archived.id)

            with self.assertRaisesRegex(ValueError, "archived"):
                uploads.create_batch(archived_scope)

    def test_terminal_batches_reject_new_files_and_status_errors_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases, uploads, _documents = self._services(path)
            scope = knowledge_bases.resolve_scope()
            batch = uploads.create_batch(scope)
            completed = uploads.update_batch(
                batch["id"],
                scope,
                status="failed",
                error_message=" provider\ntraceback\twith   secrets " + ("x" * 600),
            )

            self.assertEqual("failed", completed["status"])
            self.assertLessEqual(len(completed["error_message"]), 500)
            self.assertNotIn("\n", completed["error_message"])
            with self.assertRaisesRegex(ValueError, "does not accept"):
                uploads.add_file(
                    batch["id"],
                    scope,
                    original_name="late.md",
                    relative_path="late.md",
                    storage_path="uploads/late.md",
                    size=1,
                )
            with self.assertRaisesRegex(ValueError, "Unsupported upload batch status"):
                uploads.update_batch(batch["id"], scope, status="unknown")
            with self.assertRaisesRegex(ValueError, "Unsupported upload file status"):
                uploads.update_file("missing", scope, status="unknown")

    def test_cancel_batch_marks_unstarted_files_canceled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.sqlite3"
            knowledge_bases, uploads, documents = self._services(path)
            scope = knowledge_bases.resolve_scope()

            batch = uploads.create_batch(scope)
            first = uploads.add_file(
                batch["id"],
                scope,
                original_name="first.md",
                relative_path="first.md",
                storage_path="uploads/first.md",
                size=1,
            )
            second = uploads.add_file(
                batch["id"],
                scope,
                original_name="second.md",
                relative_path="second.md",
                storage_path="uploads/second.md",
                size=1,
            )
            documents.upsert_document(
                id="doc-1",
                name="first.md",
                file_type="md",
                storage_path="uploads/first.md",
                parse_status="parsed",
                workspace_id=scope.workspace_id,
                knowledge_base_id=scope.knowledge_base_id,
            )
            uploads.update_file(first["id"], scope, status="completed", document_id="doc-1")

            canceled = uploads.cancel_batch(batch["id"], scope)

            statuses = {item["id"]: item["status"] for item in canceled["files"]}
            self.assertEqual("canceled", canceled["status"])
            self.assertEqual("completed", statuses[first["id"]])
            self.assertEqual("canceled", statuses[second["id"]])


if __name__ == "__main__":
    unittest.main()
