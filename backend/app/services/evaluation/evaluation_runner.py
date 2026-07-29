from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any

from app.models.evaluation import EvalResultRecord, EvaluationAnswerSnapshot
from app.models.knowledge_base import KnowledgeBaseScope


class EvaluationRunner:
    def __init__(self, rag_service, repository, dataset_loader, scorer, reporter=None):
        self.rag_service = rag_service
        self.repository = repository
        self.dataset_loader = dataset_loader
        self.scorer = scorer
        self.reporter = reporter

    def run(
        self,
        dataset_path: Path | str,
        case_ids: list[str] | None = None,
        baseline_run_id: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dataset = self.dataset_loader.load(dataset_path)
        selected = [case for case in dataset.cases if not case_ids or case.id in set(case_ids)]
        selected_knowledge_base_ids = list(
            dict.fromkeys(knowledge_base_id for case in selected for knowledge_base_id in case.knowledge_base_ids)
        )
        run = self.repository.create_run(
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            dataset_path=dataset.source_path,
            config_snapshot={**(config_snapshot or {}), "knowledge_base_ids": selected_knowledge_base_ids},
            knowledge_base_ids=selected_knowledge_base_ids,
        )
        failed = 0
        for case in selected:
            started = time.perf_counter()
            try:
                resolver = getattr(self.rag_service, "resolve_scope", None)
                if callable(resolver):
                    scope = resolver(case.knowledge_base_ids or None)
                elif case.knowledge_base_ids:
                    raise RuntimeError("Evaluation RAG service does not support knowledge-base scope")
                else:
                    scope = KnowledgeBaseScope(
                        "default-workspace", ("default-knowledge-base",), compatibility_default=True
                    )
                answer_parameters = inspect.signature(self.rag_service.answer_query).parameters
                if "scope" in answer_parameters:
                    response = self.rag_service.answer_query(case.question, filters=case.filters, scope=scope)
                else:
                    response = self.rag_service.answer_query(case.question, filters=case.filters)
                response["debug_info"] = {
                    **(response.get("debug_info") or {}),
                    "knowledge_base_scope": scope.to_dict(),
                }
                latency_ms = (time.perf_counter() - started) * 1000
                snapshot = EvaluationAnswerSnapshot.from_response(response, latency_ms=latency_ms)
                scores = self.scorer.score(case, snapshot)
                passed = all(score.passed for score in scores.values() if score.name != "latency_ms")
                status = "passed" if passed else "failed"
                if not passed:
                    failed += 1
                self.repository.add_result(
                    EvalResultRecord(
                        run_id=run["id"],
                        case_id=case.id,
                        status=status,
                        question=case.question,
                        query_type=case.query_type,
                        tags=case.tags,
                        knowledge_base_ids=list(scope.selected_knowledge_base_ids),
                        case_snapshot=case.to_dict(),
                        answer=snapshot.answer,
                        response_snapshot=snapshot.to_response_snapshot(),
                        evidence_snapshot=snapshot.to_evidence_snapshot(),
                        metric_scores={name: score.to_dict() for name, score in scores.items()},
                        latency_ms=latency_ms,
                    )
                )
            except Exception as exc:
                failed += 1
                latency_ms = (time.perf_counter() - started) * 1000
                self.repository.add_result(
                    EvalResultRecord(
                        run_id=run["id"],
                        case_id=case.id,
                        status="failed",
                        question=case.question,
                        query_type=case.query_type,
                        tags=case.tags,
                        knowledge_base_ids=list(case.knowledge_base_ids),
                        case_snapshot=case.to_dict(),
                        latency_ms=latency_ms,
                        error_message=str(exc),
                    )
                )
        results = self.repository.list_results(run["id"])
        status = "completed" if failed == 0 else "failed" if failed == len(selected) else "partial_failed"
        aggregate_scores = self.reporter.aggregate_scores(results) if self.reporter else {}
        report_paths = self.reporter.generate(run["id"], baseline_run_id=baseline_run_id) if self.reporter else {}
        return self.repository.finish_run(run["id"], status=status, aggregate_scores=aggregate_scores, report_paths=report_paths)


class EvaluationService:
    def __init__(self, runner: EvaluationRunner, repository):
        self.runner = runner
        self.repository = repository

    def start_run(self, dataset_path: str, case_ids: list[str] | None = None, baseline_run_id: str | None = None) -> dict[str, Any]:
        return self.runner.run(dataset_path, case_ids=case_ids, baseline_run_id=baseline_run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        return self.repository.list_runs()

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.repository.get_run(run_id)

    def list_results(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_results(run_id)
