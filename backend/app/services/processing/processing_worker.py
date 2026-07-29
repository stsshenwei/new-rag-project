from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.models.knowledge_base import KnowledgeBaseScope
from app.models.processing_config import DurableProcessingWorkerConfig
from app.services.infrastructure.logging_config import get_trace_id, trace_context
from app.services.infrastructure.observability import use_observability_trace
from app.services.processing.processing_task_repository import ProcessingTaskRepository

if TYPE_CHECKING:
    from app.services.retrieval.rag_service import RAGService


logger = logging.getLogger(__name__)

UPLOAD_FILE_TASK = "upload_file.process"


class DocumentProcessingWorker:
    def __init__(
        self,
        *,
        repository: ProcessingTaskRepository,
        rag_service: "RAGService",
        config: DurableProcessingWorkerConfig | None = None,
        worker_id: str | None = None,
    ):
        self.repository = repository
        self.rag_service = rag_service
        self.config = config or DurableProcessingWorkerConfig()
        self.worker_id = worker_id or f"worker-{uuid4().hex[:12]}"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def enqueue_upload_batch(self, batch_id: str, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        batch = self.rag_service.upload_batch_repository.get_batch(batch_id, scope)
        tasks: list[dict[str, Any]] = []
        for file_task in batch.get("files", []):
            if str(file_task.get("status", "")) in {"completed", "canceled"}:
                continue
            document_id = str(file_task.get("document_id") or "")
            tasks.append(
                self.repository.create_task(
                    UPLOAD_FILE_TASK,
                    scope,
                    payload={
                        "batch_id": batch_id,
                        "file_id": file_task.get("id"),
                        "storage_path": file_task.get("storage_path"),
                        "original_name": file_task.get("original_name"),
                    },
                    document_id=document_id,
                    upload_batch_id=batch_id,
                    upload_file_id=str(file_task.get("id") or ""),
                    max_attempts=self.config.default_max_attempts,
                    trace_id=get_trace_id(),
                )
            )
        logger.info(
            "processing_worker.enqueue_upload_batch",
            extra={
                "workspace_id": scope.workspace_id,
                "knowledge_base_id": scope.knowledge_base_id,
                "batch_id": batch_id,
                "tasks": len(tasks),
            },
        )
        return tasks

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run_forever, name=self.worker_id, daemon=True)
        self._thread.start()
        logger.info("processing_worker.start", extra={"worker_id": self.worker_id})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("processing_worker.stop", extra={"worker_id": self.worker_id})

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            processed = self.run_once()
            if not processed:
                self._stop_event.wait(self.config.poll_interval_seconds)

    def run_once(self) -> bool:
        task = self.repository.claim_next(
            self.worker_id,
            lease_seconds=self.config.lease_timeout_seconds,
            task_types={UPLOAD_FILE_TASK},
        )
        if task is None:
            return False
        self._process_claimed_task(task)
        return True

    def _process_claimed_task(self, task: dict[str, Any]) -> None:
        task_trace_id = str(task.get("trace_id") or "")
        with trace_context(task_trace_id or None):
            with use_observability_trace(task_trace_id or None, name=f"processing_worker.{task.get('task_type')}"):
                logger.info(
                    "processing_worker.task.start",
                    extra={
                        "worker_id": self.worker_id,
                        "task_id": task.get("id"),
                        "task_type": task.get("task_type"),
                        "attempt": task.get("attempt"),
                    },
                )
                try:
                    if task["task_type"] == UPLOAD_FILE_TASK:
                        self._process_upload_file_task(task)
                    else:
                        raise ValueError(f"Unsupported processing task type: {task['task_type']}")
                    self.repository.complete(str(task["id"]), worker_id=self.worker_id)
                    logger.info("processing_worker.task.completed", extra={"worker_id": self.worker_id, "task_id": task.get("id")})
                except ProcessingTaskCanceled as exc:
                    self.repository.cancel_task(str(task["id"]), reason=str(exc))
                    logger.info("processing_worker.task.canceled", extra={"worker_id": self.worker_id, "task_id": task.get("id")})
                except Exception as exc:
                    self._handle_task_failure(task, exc)

    def _process_upload_file_task(self, task: dict[str, Any]) -> None:
        scope = KnowledgeBaseScope(
            workspace_id=str(task["workspace_id"]),
            selected_knowledge_base_ids=(str(task["knowledge_base_id"]),),
        )
        payload = task.get("payload") or {}
        batch_id = str(task.get("upload_batch_id") or payload.get("batch_id") or "")
        file_id = str(task.get("upload_file_id") or payload.get("file_id") or "")
        file_task = self.rag_service.upload_batch_repository.get_file(file_id, scope)
        self._ensure_upload_file_active(file_id, batch_id, scope)

        self.rag_service._process_upload_file(
            file_task,
            scope,
            cancel_check=lambda: self._ensure_upload_file_active(file_id, batch_id, scope),
        )
        updated_file = self.rag_service.upload_batch_repository.get_file(file_id, scope)
        if str(updated_file.get("status")) == "failed":
            raise RuntimeError(str(updated_file.get("error_message") or "Upload file processing failed"))
        self._ensure_upload_file_active(file_id, batch_id, scope)
        self.rag_service._finish_upload_batch_from_files(batch_id, scope)

    def _ensure_upload_file_active(self, file_id: str, batch_id: str, scope: KnowledgeBaseScope) -> None:
        file_task = self.rag_service.upload_batch_repository.get_file(file_id, scope)
        if str(file_task.get("status")) == "canceled":
            raise ProcessingTaskCanceled(f"Upload file {file_id} was canceled")
        batch = self.rag_service.upload_batch_repository.get_batch(batch_id, scope)
        if str(batch.get("status")) == "canceled":
            raise ProcessingTaskCanceled(f"Upload batch {batch_id} was canceled")

    def _handle_task_failure(self, task: dict[str, Any], exc: Exception) -> None:
        task_id = str(task["id"])
        attempt = int(task.get("attempt", 0) or 0)
        max_attempts = int(task.get("max_attempts", self.config.default_max_attempts) or self.config.default_max_attempts)
        error_code = exc.__class__.__name__
        error_message = str(exc)
        if attempt < max_attempts:
            delay = self.config.retry_delay_for_attempt(attempt)
            self.repository.retry(
                task_id,
                error_code=error_code,
                error_message=error_message,
                delay_seconds=delay,
                worker_id=self.worker_id,
            )
            logger.warning(
                "processing_worker.task.retry",
                extra={
                    "worker_id": self.worker_id,
                    "task_id": task_id,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "delay_seconds": delay,
                    "error_type": error_code,
                    "error_message": error_message,
                },
            )
            return
        self.repository.dead_letter(task_id, error_code=error_code, error_message=error_message, worker_id=self.worker_id)
        self._reconcile_failed_upload_task(task, error_message)
        logger.exception(
            "processing_worker.task.dead_lettered",
            extra={
                "worker_id": self.worker_id,
                "task_id": task_id,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "error_type": error_code,
                "error_message": error_message,
            },
        )

    def _reconcile_failed_upload_task(self, task: dict[str, Any], error_message: str) -> None:
        try:
            scope = KnowledgeBaseScope(
                workspace_id=str(task["workspace_id"]),
                selected_knowledge_base_ids=(str(task["knowledge_base_id"]),),
            )
            file_id = str(task.get("upload_file_id") or "")
            batch_id = str(task.get("upload_batch_id") or "")
            if file_id:
                self.rag_service.upload_batch_repository.update_file(
                    file_id,
                    scope,
                    status="failed",
                    error_message=error_message,
                    retry_eligible=True,
                )
            if batch_id:
                self.rag_service._finish_upload_batch_from_files(batch_id, scope)
        except Exception:
            logger.exception("processing_worker.task.reconcile_failed_upload_failed", extra={"task_id": task.get("id")})


class ProcessingTaskCanceled(RuntimeError):
    pass


def drain_worker(worker: DocumentProcessingWorker, *, limit: int = 100) -> int:
    processed = 0
    while processed < limit and worker.run_once():
        processed += 1
        time.sleep(0)
    return processed
