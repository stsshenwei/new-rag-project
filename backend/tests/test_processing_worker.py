import tempfile
import unittest
from pathlib import Path

from app.models.processing_config import DurableProcessingWorkerConfig
from app.services.documents.document_repository import DocumentRepository
from app.services.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService
from app.services.processing.processing_task_repository import (
    TASK_CANCELED,
    TASK_COMPLETED,
    TASK_DEAD_LETTERED,
    TASK_PROCESSING,
    TASK_RETRYING,
    ProcessingTaskRepository,
)
from app.services.processing.processing_span_tracker import ProcessingSpanRepository, ProcessingSpanTracker
from app.services.processing.processing_trace import ProcessingTraceRecorder
from app.services.processing.processing_worker import DocumentProcessingWorker, drain_worker
from app.services.documents.document_parser import stable_doc_id
from tests.test_rag_service_structured_ingest import FakeParser, FakeVectorStore, make_service


class ProcessingWorkerTests(unittest.TestCase):
    def test_worker_enqueues_and_processes_upload_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            service = make_service(tmp, repo, FakeVectorStore(tmp / "vectors"), FakeParser(), knowledge_base_service=kb_service)
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True, retry_backoff_seconds=(0,), default_max_attempts=2),
                worker_id="test-worker",
            )
            service.processing_worker = worker

            batch = service.create_upload_batch(scope)
            uploaded = service.add_upload_batch_file(batch["id"], filename="manual.md", content=b"# Manual\n\nBody", scope=scope)
            started = service.start_upload_batch_processing(batch["id"], scope)
            expected_doc_id = stable_doc_id(tmp / str(uploaded["storage_path"]))
            pending_documents = service.list_documents(scope)
            queued_file = service.get_upload_batch(batch["id"], scope)["files"][0]
            queued_task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]

            self.assertEqual("processing", started["status"])
            self.assertEqual(1, len(pending_documents))
            self.assertEqual(expected_doc_id, pending_documents[0]["id"])
            self.assertEqual("pending", pending_documents[0]["parse_status"])
            self.assertEqual(expected_doc_id, queued_file["document_id"])
            self.assertEqual(1, len(task_repo.list_tasks(scope, upload_batch_id=batch["id"])))
            self.assertEqual(expected_doc_id, queued_task["document_id"])
            self.assertEqual(1, drain_worker(worker))
            task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]
            self.assertEqual(TASK_COMPLETED, task["status"])
            completed = service.get_upload_batch(batch["id"], scope)
            self.assertEqual("completed", completed["status"])
            self.assertEqual("completed", completed["files"][0]["status"])

    def test_worker_retries_then_dead_letters_failed_upload_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            service = make_service(tmp, repo, FakeVectorStore(tmp / "vectors"), AlwaysFailParser(), knowledge_base_service=kb_service)
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True, retry_backoff_seconds=(0,), default_max_attempts=2),
                worker_id="test-worker",
            )
            service.processing_worker = worker

            batch = service.create_upload_batch(scope)
            service.add_upload_batch_file(batch["id"], filename="manual.md", content=b"# Manual\n\nBody", scope=scope)
            service.start_upload_batch_processing(batch["id"], scope)

            self.assertTrue(worker.run_once())
            task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]
            self.assertEqual(TASK_RETRYING, task["status"])
            self.assertTrue(worker.run_once())
            task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]
            self.assertEqual(TASK_DEAD_LETTERED, task["status"])
            self.assertEqual(1, len(task_repo.list_dead_letters(scope)))
            failed = service.get_upload_batch(batch["id"], scope)
            self.assertEqual("failed", failed["status"])
            self.assertEqual("failed", failed["files"][0]["status"])

    def test_cancel_upload_batch_cancels_queued_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            service = make_service(tmp, repo, FakeVectorStore(tmp / "vectors"), FakeParser(), knowledge_base_service=kb_service)
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True),
                worker_id="test-worker",
            )
            service.processing_worker = worker

            batch = service.create_upload_batch(scope)
            service.add_upload_batch_file(batch["id"], filename="manual.md", content=b"# Manual\n\nBody", scope=scope)
            service.start_upload_batch_processing(batch["id"], scope)
            service.cancel_upload_batch(batch["id"], scope)

            task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]
            self.assertEqual(TASK_CANCELED, task["status"])
            self.assertFalse(worker.run_once())

    def test_worker_recovers_stale_leased_upload_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            service = make_service(tmp, repo, FakeVectorStore(tmp / "vectors"), FakeParser(), knowledge_base_service=kb_service)
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            stalled_worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True, lease_timeout_seconds=0),
                worker_id="stalled-worker",
            )
            service.processing_worker = stalled_worker

            batch = service.create_upload_batch(scope)
            service.add_upload_batch_file(batch["id"], filename="manual.md", content=b"# Manual\n\nBody", scope=scope)
            service.start_upload_batch_processing(batch["id"], scope)
            claimed = task_repo.claim_next("stalled-worker", lease_seconds=0)
            self.assertIsNotNone(claimed)
            self.assertEqual(TASK_PROCESSING, claimed["status"])

            recovery_worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True, retry_backoff_seconds=(0,)),
                worker_id="recovery-worker",
            )
            service.processing_worker = recovery_worker
            self.assertTrue(recovery_worker.run_once())
            task = task_repo.list_tasks(scope, upload_batch_id=batch["id"])[0]
            self.assertEqual(TASK_COMPLETED, task["status"])

    def test_list_documents_exposes_processing_runtime_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            trace_recorder = ProcessingTraceRecorder.from_env(
                tmp / "traces",
                span_tracker=ProcessingSpanTracker(ProcessingSpanRepository(repo.db_path, repo.defaults)),
            )
            service = make_service(
                tmp,
                repo,
                FakeVectorStore(tmp / "vectors"),
                FakeParser(),
                knowledge_base_service=kb_service,
                processing_trace_recorder=trace_recorder,
            )
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True),
                worker_id="test-worker",
            )
            service.processing_worker = worker
            repo.upsert_document("doc-1", "manual.md", "md", "manual.md", "parsed")
            repo.update_enrichment(scope=scope, doc_id="doc-1", status="completed", summary="Short summary")
            _, attempt = trace_recorder.span_tracker.open_attempt(knowledge_id="doc-1", input={"file": "manual.md"})
            task = task_repo.create_task(
                "process_document",
                scope,
                document_id="doc-1",
                payload={"doc_id": "doc-1"},
                max_attempts=2,
            )
            claimed = task_repo.claim_next("test-worker")
            self.assertEqual(task["id"], claimed["id"])
            task_repo.dead_letter(claimed["id"], error_code="PARSER", error_message="parser unavailable", worker_id="test-worker")

            document = service.list_documents(scope)[0]

            self.assertTrue(document["summary_available"])
            self.assertEqual(TASK_DEAD_LETTERED, document["processing_task_status"])
            self.assertTrue(document["processing_dead_lettered"])
            self.assertEqual("parser unavailable", document["processing_last_error"])
            self.assertEqual(1, document["processing_task_attempt"])
            self.assertEqual(2, document["processing_task_max_attempts"])
            self.assertEqual(attempt, document["processing_latest_attempt"])

    def test_delete_document_cancels_tasks_and_open_spans(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo = DocumentRepository(tmp / "metadata.sqlite3")
            kb_service = KnowledgeBaseService(KnowledgeBaseRepository(repo.db_path, repo.defaults))
            scope = kb_service.resolve_scope()
            trace_recorder = ProcessingTraceRecorder.from_env(
                tmp / "traces",
                span_tracker=ProcessingSpanTracker(ProcessingSpanRepository(repo.db_path, repo.defaults)),
            )
            service = make_service(
                tmp,
                repo,
                FakeVectorStore(tmp / "vectors"),
                FakeParser(),
                knowledge_base_service=kb_service,
                processing_trace_recorder=trace_recorder,
            )
            task_repo = ProcessingTaskRepository(repo.db_path, repo.defaults)
            worker = DocumentProcessingWorker(
                repository=task_repo,
                rag_service=service,
                config=DurableProcessingWorkerConfig(enabled=True),
                worker_id="test-worker",
            )
            service.processing_worker = worker
            repo.upsert_document("doc-1", "manual.md", "md", "manual.md", "parsing")
            task = task_repo.create_task("process_document", scope, document_id="doc-1", payload={"doc_id": "doc-1"})
            root, attempt = trace_recorder.span_tracker.open_attempt(knowledge_id="doc-1", input={"file": "manual.md"})
            self.assertIsNotNone(root)
            trace_recorder.span_tracker.begin_stage("doc-1", attempt, "docreader", {"parser": "fixture"})

            service.delete_document("doc-1", scope)

            self.assertEqual(TASK_CANCELED, task_repo.get_task(task["id"])["status"])
            tree = trace_recorder.span_tracker.latest_tree("doc-1")
            self.assertIsNotNone(tree)
            self.assertEqual("cancelled", tree["root"]["status"])


class AlwaysFailParser(FakeParser):
    def parse(self, file_path):
        raise RuntimeError("parser unavailable")


if __name__ == "__main__":
    unittest.main()
