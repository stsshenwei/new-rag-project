import unittest

from app.services.retrieval_models import Answer, BuiltContext, Citation, RetrievedChunk


class RetrievalModelTests(unittest.TestCase):
    def test_retrieved_chunk_and_answer_shapes_are_traceable(self):
        chunk = RetrievedChunk(
            chunk_id="c1",
            doc_id="doc-1",
            parent_id="p1",
            score=0.8,
            bm25_score=2.1,
            title_path="Manual/Errors",
            page_start=3,
            page_end=4,
        )
        context = BuiltContext(question="q", text="ctx", selected_parent_chunks=[{"parent_id": "p1"}], token_count=10)
        citation = Citation(
            doc_id=chunk.doc_id,
            file_name="manual.pdf",
            chunk_id=chunk.chunk_id,
            parent_id=chunk.parent_id,
            title_path=chunk.title_path,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            summary="summary",
        )
        answer = Answer(answer="a", citations=[citation], used_chunks=[chunk.chunk_id], confidence=0.7, debug_info=None)

        self.assertEqual("p1", context.selected_parent_chunks[0]["parent_id"])
        self.assertEqual("c1", answer.used_chunks[0])
        self.assertEqual("Manual/Errors", answer.citations[0].title_path)


if __name__ == "__main__":
    unittest.main()
