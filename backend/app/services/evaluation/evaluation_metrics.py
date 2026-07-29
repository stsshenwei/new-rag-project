from __future__ import annotations

from typing import Protocol

from app.models.evaluation import EvalCase, EvaluationAnswerSnapshot, MetricScore
from app.services.retrieval.citation_verifier import CitationVerifier


class EvaluationJudgeProvider(Protocol):
    def judge(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> dict[str, MetricScore]:
        ...


class AnswerCorrectnessJudgeProvider(Protocol):
    def judge_answer_correctness(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        ...


class FaithfulnessJudgeProvider(Protocol):
    def judge_faithfulness(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        ...


class CitationJudgeProvider(Protocol):
    def judge_citation_quality(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        ...


class NoOpEvaluationJudgeProvider:
    def judge(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> dict[str, MetricScore]:
        return {
            "judge_answer_correctness": MetricScore(
                "judge_answer_correctness",
                0.0,
                True,
                "judge provider disabled",
                {"skipped": True},
            )
        }


class RuleBasedEvaluationScorer:
    def __init__(self, document_repository, judge_provider: EvaluationJudgeProvider | None = None):
        self.document_repository = document_repository
        self.citation_verifier = CitationVerifier(document_repository)
        self.judge_provider = judge_provider or NoOpEvaluationJudgeProvider()

    def score(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> dict[str, MetricScore]:
        scores = {
            "citation_resolvable_rate": self._score_citations(snapshot),
            "required_source_hit_rate": self._score_sources(case, snapshot),
            "answer_contains_expected_terms": self._score_terms(case, snapshot),
            "graph_path_traceability_rate": self._score_graph(snapshot),
            "tool_plan_match_rate": self._score_tools(case, snapshot),
            "insufficient_evidence_correctness": self._score_insufficient(case, snapshot),
            "latency_ms": MetricScore("latency_ms", float(snapshot.latency_ms or 0.0), True, "latency captured"),
        }
        scores.update(self.judge_provider.judge(case, snapshot))
        return scores

    def _score_citations(self, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        verification = self.citation_verifier.verify(snapshot.citations, snapshot.used_chunks, snapshot.graph_paths)
        checked = len(snapshot.citations) + len(snapshot.used_chunks)
        score = 1.0 if checked == 0 else (len(verification.verified_citations) + len(verification.verified_chunks)) / max(checked, 1)
        return MetricScore("citation_resolvable_rate", min(score, 1.0), verification.valid, verification.summary, verification.to_dict())

    def _score_sources(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        expected_chunks = set(case.expected_source_chunk_ids)
        expected_docs = set(case.expected_source_doc_ids)
        used_chunks = set(snapshot.used_chunks)
        citation_chunks = {str(item.get("chunk_id") or item.get("child_id") or item.get("parent_id") or "") for item in snapshot.citations}
        citation_docs = {str(item.get("doc_id") or "") for item in snapshot.citations}
        expected_count = len(expected_chunks) + len(expected_docs)
        if expected_count == 0:
            return MetricScore("required_source_hit_rate", 1.0, True, "no required sources")
        hits = len(expected_chunks & (used_chunks | citation_chunks)) + len(expected_docs & citation_docs)
        score = hits / max(expected_count, 1)
        return MetricScore("required_source_hit_rate", score, hits == expected_count, f"{hits}/{expected_count} expected sources matched")

    def _score_terms(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        terms = case.expected_answer_terms
        if not terms:
            return MetricScore("answer_contains_expected_terms", 1.0, True, "no expected terms")
        answer = snapshot.answer.casefold()
        hits = [term for term in terms if str(term).casefold() in answer]
        return MetricScore("answer_contains_expected_terms", len(hits) / len(terms), len(hits) == len(terms), f"{len(hits)}/{len(terms)} expected terms matched")

    def _score_graph(self, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        relations = []
        for path in snapshot.graph_paths:
            relations.extend([item for item in path.get("relations", []) if isinstance(item, dict)])
        if not relations:
            return MetricScore("graph_path_traceability_rate", 1.0, True, "no graph paths returned")
        resolved = [relation for relation in relations if relation.get("source_chunk_id") and self.document_repository.get_chunk(str(relation.get("source_chunk_id")))]
        return MetricScore("graph_path_traceability_rate", len(resolved) / len(relations), len(resolved) == len(relations), f"{len(resolved)}/{len(relations)} graph relations traceable")

    def _score_tools(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        used = {str(call.get("tool") or "") for call in snapshot.tool_calls}
        expected = set(case.expected_tools)
        forbidden = set(case.forbidden_tools)
        expected_ok = expected.issubset(used)
        forbidden_ok = not (forbidden & used)
        passed = expected_ok and forbidden_ok
        checks = len(expected) + len(forbidden)
        score = 1.0 if checks == 0 else (int(expected_ok) + int(forbidden_ok)) / 2
        return MetricScore("tool_plan_match_rate", score, passed, "tool expectations matched" if passed else "tool expectations failed", {"used_tools": sorted(used)})

    def _score_insufficient(self, case: EvalCase, snapshot: EvaluationAnswerSnapshot) -> MetricScore:
        if not case.expect_insufficient_evidence:
            return MetricScore("insufficient_evidence_correctness", 1.0, True, "not an insufficient-evidence case")
        text = snapshot.answer.casefold()
        matched = any(phrase in text for phrase in ["cannot determine", "insufficient", "无法确定", "证据不足"])
        return MetricScore("insufficient_evidence_correctness", 1.0 if matched else 0.0, matched, "insufficient evidence response checked")
