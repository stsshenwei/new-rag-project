import unittest

from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.retrieval.retrieval_models import RetrievedChunk


class FakeEmbedding:
    def __init__(self):
        self.queries = []

    def embed_text(self, text):
        self.queries.append(text)
        return [0.1, 0.2]


class FakeDenseSearch:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, embedding, top_k, filters):
        self.calls.append((embedding, top_k, filters))
        return self.results[:top_k]


class FakeKeywordSearch:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, top_k, filters):
        self.calls.append((query, top_k, filters))
        return self.results[:top_k]


class HybridRetrieverTests(unittest.TestCase):
    def test_retrieve_embeds_question_and_fuses_dense_keyword_with_rrf(self):
        embedding = FakeEmbedding()
        dense = FakeDenseSearch(
            [
                RetrievedChunk("shared", "doc-1", "p1", score=0.9),
                RetrievedChunk("dense-only", "doc-1", "p2", score=0.8),
            ]
        )
        keyword = FakeKeywordSearch(
            [
                RetrievedChunk("shared", "doc-1", "p1", score=3.0),
                RetrievedChunk("keyword-only", "doc-2", "p3", score=2.0),
            ]
        )
        retriever = HybridRetriever(embedding, dense, keyword)

        results = retriever.retrieve("ERR_CODE_42", top_k=30, filters={"doc_ids": ["doc-1", "doc-2"]})

        self.assertEqual(["ERR_CODE_42"], embedding.queries)
        self.assertEqual([0.1, 0.2], dense.calls[0][0])
        self.assertEqual(50, dense.calls[0][1])
        self.assertEqual(50, keyword.calls[0][1])
        self.assertEqual({"doc_ids": ["doc-1", "doc-2"]}, keyword.calls[0][2])
        self.assertEqual(["shared", "dense-only", "keyword-only"], [item.chunk_id for item in results])
        self.assertEqual(0.9, results[0].vector_score)
        self.assertEqual(3.0, results[0].bm25_score)

    def test_weighted_fusion_is_available(self):
        retriever = HybridRetriever(
            FakeEmbedding(),
            FakeDenseSearch([RetrievedChunk("dense", "doc-1", "p1", score=0.2)]),
            FakeKeywordSearch([RetrievedChunk("keyword", "doc-1", "p2", score=2.0)]),
            fusion_strategy="weighted",
            dense_weight=0.7,
            keyword_weight=0.3,
        )

        results = retriever.retrieve("timeout")

        self.assertEqual("keyword", results[0].chunk_id)
        self.assertAlmostEqual(0.6, results[0].hybrid_score)


if __name__ == "__main__":
    unittest.main()
