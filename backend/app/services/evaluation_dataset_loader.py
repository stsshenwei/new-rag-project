from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.evaluation import SUPPORTED_EVAL_SCHEMA_VERSION, EvaluationDataset


class EvaluationDatasetLoader:
    def __init__(self, allowed_roots: list[Path | str]):
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def load(self, dataset_path: Path | str) -> EvaluationDataset:
        path = self._resolve_dataset_path(dataset_path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        elif suffix in {".yaml", ".yml"}:
            data = self._load_yaml(path)
        else:
            raise ValueError("Evaluation dataset must be a JSON or YAML file")
        dataset = EvaluationDataset.from_dict(data, source_path=str(path))
        self._validate(dataset)
        return dataset

    def _resolve_dataset_path(self, dataset_path: Path | str) -> Path:
        raw = Path(dataset_path)
        candidates = [raw] if raw.is_absolute() else [root / raw for root in self.allowed_roots]
        for candidate in candidates:
            resolved = candidate.resolve()
            if any(_is_relative_to(resolved, root) for root in self.allowed_roots) and resolved.exists():
                return resolved
        raise ValueError("Evaluation dataset path is outside allowed roots or does not exist")

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise ValueError("YAML evaluation datasets require PyYAML to be installed") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _validate(self, dataset: EvaluationDataset) -> None:
        if dataset.schema_version != SUPPORTED_EVAL_SCHEMA_VERSION:
            raise ValueError(f"Unsupported evaluation dataset schema: {dataset.schema_version}")
        if not dataset.id or not dataset.name or not dataset.version:
            raise ValueError("Evaluation dataset requires id, name, and version")
        if not dataset.cases:
            raise ValueError("Evaluation dataset requires at least one case")
        seen = set()
        for case in dataset.cases:
            if not case.id or not case.question:
                raise ValueError("Evaluation case requires id and question")
            if case.id in seen:
                raise ValueError(f"Duplicate evaluation case id: {case.id}")
            seen.add(case.id)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
