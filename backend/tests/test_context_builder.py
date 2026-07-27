import unittest

from app.services.context_builder import ContextBuilder
from app.services.retrieval_models import RetrievedChunk


class FakeRepository:
    def __init__(self):
        self.parents = {
            "p1": {
                "id": "p1",
                "doc_id": "doc-1",
                "title_path": "Manual/Install",
                "content": "Parent one content",
                "content_markdown": "Parent one content",
                "page_start": 1,
                "page_end": 2,
                "metadata_json": {"file_name": "manual.pdf"},
            },
            "p2": {
                "id": "p2",
                "doc_id": "doc-1",
                "title_path": "Manual/Errors",
                "content": "Parent two content " * 30,
                "content_markdown": "Parent two content " * 30,
                "page_start": 3,
                "page_end": 4,
                "metadata_json": {"file_name": "manual.pdf"},
            },
        }
        self.children = [
            {"id": "c0", "doc_id": "doc-1", "chunk_type": "child"},
            {"id": "c1", "doc_id": "doc-1", "chunk_type": "child"},
            {"id": "c2", "doc_id": "doc-1", "chunk_type": "child"},
        ]

    def get_chunk(self, chunk_id):
        return self.parents.get(chunk_id)

    def list_chunks(self, doc_id=None, chunk_types=None):
        return [child for child in self.children if child["doc_id"] == doc_id and child["chunk_type"] in chunk_types]


class ContextBuilderTests(unittest.TestCase):
    def test_build_deduplicates_parents_and_merges_child_refs(self):
        builder = ContextBuilder(FakeRepository(), max_tokens=8000, include_neighbor_chunks=True)

        context = builder.build(
            "question",
            [
                RetrievedChunk("c1", "doc-1", "p1", content="hit one", score=0.8),
                RetrievedChunk("c2", "doc-1", "p1", content="hit two", score=0.7),
            ],
        )

        self.assertEqual(1, len(context.selected_parent_chunks))
        parent = context.selected_parent_chunks[0]
        self.assertEqual("manual.pdf", parent["file_name"])
        self.assertEqual("Manual/Install", parent["title_path"])
        self.assertEqual(["c1", "c2"], [child["chunk_id"] for child in parent["matched_children"]])
        self.assertIn("c0", parent["neighbor_chunk_ids"])
        self.assertIn("Parent one content", context.text)

    def test_build_respects_token_budget_by_score(self):
        builder = ContextBuilder(FakeRepository(), max_tokens=10, include_neighbor_chunks=False)

        context = builder.build(
            "question",
            [
                RetrievedChunk("c2", "doc-1", "p2", content="large", score=0.2),
                RetrievedChunk("c1", "doc-1", "p1", content="small", score=0.9),
            ],
        )

        self.assertEqual(["p1"], [item["parent_id"] for item in context.selected_parent_chunks])


if __name__ == "__main__":
    unittest.main()
