from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

TEXT_PATHS = [
    "backend/config/prompt_templates",
    "backend/app/services/adaptive_chunker.py",
    "backend/app/services/document_chunker.py",
    "backend/app/services/agent_runtime_tools.py",
    "backend/app/services/agent_prompt_templates.py",
    "backend/app/services/rag_service.py",
    "frontend/app/knowledge/page.tsx",
    "frontend/app/chat/page.tsx",
    "frontend/app/components",
    "docs/design-docs/weknora-core-parity-map.md",
]

TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".ts", ".tsx", ".css", ".md"}
MOJIBAKE_MARKERS = (
    "\ufffd",
    "锛",
    "绗",
    "銆",
    "鈥",
    "龤",
)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for relative in TEXT_PATHS:
        path = REPO_ROOT / relative
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(item for item in path.rglob("*") if item.suffix in TEXT_SUFFIXES))
    return sorted(set(files))


class Utf8IntegrityTests(unittest.TestCase):
    def test_prompt_and_runtime_text_files_are_valid_utf8(self):
        checked = iter_text_files()
        self.assertTrue(checked)
        for path in checked:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                path.read_text(encoding="utf-8")

    def test_required_prompt_and_runtime_files_do_not_contain_mojibake_markers(self):
        offenders: list[str] = []
        for path in iter_text_files():
            text = path.read_text(encoding="utf-8")
            for marker in MOJIBAKE_MARKERS:
                if marker in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} contains {marker!r}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
