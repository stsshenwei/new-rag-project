from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EvaluationReporter:
    def __init__(self, report_dir: Path | str, repository):
        self.report_dir = Path(report_dir)
        self.repository = repository
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def aggregate_scores(self, results: list[dict[str, Any]]) -> dict[str, float]:
        buckets: dict[str, list[float]] = {}
        for result in results:
            for name, score in (result.get("metric_scores") or {}).items():
                if isinstance(score, dict) and isinstance(score.get("score"), (int, float)):
                    buckets.setdefault(name, []).append(float(score["score"]))
        return {name: round(sum(values) / len(values), 4) for name, values in buckets.items() if values}

    def generate(self, run_id: str, baseline_run_id: str | None = None) -> dict[str, str]:
        run = self.repository.get_run(run_id)
        results = self.repository.list_results(run_id)
        aggregates = self.aggregate_scores(results)
        comparison = self.compare_runs(run_id, baseline_run_id) if baseline_run_id else {}
        payload = {"run": run, "aggregate_scores": aggregates, "results": results, "comparison": comparison}
        json_path = self.report_dir / f"{run_id}.json"
        markdown_path = self.report_dir / f"{run_id}.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(self._markdown(payload), encoding="utf-8")
        return {"json": str(json_path), "markdown": str(markdown_path)}

    def compare_runs(self, run_id: str, baseline_run_id: str | None) -> dict[str, Any]:
        if not baseline_run_id:
            return {}
        current = self.repository.list_results(run_id)
        baseline = self.repository.list_results(baseline_run_id)
        current_scores = self.aggregate_scores(current)
        baseline_scores = self.aggregate_scores(baseline)
        deltas = {name: round(current_scores.get(name, 0.0) - baseline_scores.get(name, 0.0), 4) for name in set(current_scores) | set(baseline_scores)}
        current_status = {item["case_id"]: item["status"] for item in current}
        baseline_status = {item["case_id"]: item["status"] for item in baseline}
        return {
            "metric_deltas": deltas,
            "newly_failed_cases": [case_id for case_id, status in current_status.items() if status == "failed" and baseline_status.get(case_id) != "failed"],
            "fixed_cases": [case_id for case_id, status in current_status.items() if status != "failed" and baseline_status.get(case_id) == "failed"],
        }

    def _markdown(self, payload: dict[str, Any]) -> str:
        run = payload["run"]
        lines = [
            f"# Evaluation Report: {run['id']}",
            "",
            f"- Dataset: `{run['dataset_id']}` `{run['dataset_version']}`",
            f"- Status: `{run['status']}`",
            "",
            "## Aggregate Scores",
            "",
        ]
        for name, score in sorted(payload["aggregate_scores"].items()):
            lines.append(f"- `{name}`: {score}")
        lines.extend(["", "## Failed Cases", ""])
        failed = [item for item in payload["results"] if item.get("status") == "failed"]
        if not failed:
            lines.append("- None")
        for item in failed:
            lines.append(f"- `{item['case_id']}`: {item.get('error_message', '')}")
        lines.extend(["", "## Case Summary", ""])
        for item in payload["results"]:
            lines.append(f"- `{item['case_id']}`: {item['status']} ({item.get('latency_ms', 0)} ms)")
        return "\n".join(lines) + "\n"
