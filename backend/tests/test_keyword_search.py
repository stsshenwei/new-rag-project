import unittest
import tempfile
from pathlib import Path

from app.models.document_models import Chunk
from app.services.document_repository import DocumentRepository
from app.services.keyword_search import MilvusKeywordSearch, SQLiteFTSKeywordSearch


class FakeMilvusStore:
    def __init__(self):
        self.indexed = []
        self.deleted = []
        self.queries = []
        self.bm25_hits = []

    def upsert_chunks(self, chunks):
        self.indexed.extend(chunks)

    def query_bm25(self, query, top_k):
        self.queries.append((query, top_k))
        return self.bm25_hits[:top_k]

    def delete_document(self, doc_id):
        self.deleted.append(doc_id)


class KeywordSearchTests(unittest.TestCase):
    def test_index_delegates_to_milvus_store(self):
        store = FakeMilvusStore()
        keyword_search = MilvusKeywordSearch(store)
        chunk = Chunk("c1", "doc-1", "p1", "child", "API", "ERR_CODE_42", "ERR_CODE_42", 1, 1, 3, {})

        keyword_search.index([chunk])

        self.assertEqual([chunk], store.indexed)

    def test_search_returns_traceable_results(self):
        store = FakeMilvusStore()
        store.bm25_hits = [
            {
                "content": "Use --timeout 30 with v1.2.3",
                "metadata": {
                    "chunk_id": "c1",
                    "doc_id": "doc-1",
                    "parent_id": "p1",
                    "chunk_type": "child",
                    "title_path": "CLI/Flags",
                    "page_start": 7,
                    "page_end": 7,
                },
                "bm25_score": 3.14,
            }
        ]
        keyword_search = MilvusKeywordSearch(store)

        results = keyword_search.search("ERR_CODE_42 --timeout v1.2.3", top_k=5, filters={"doc_ids": ["doc-1"]})

        self.assertEqual([("ERR_CODE_42 --timeout v1.2.3", 5)], store.queries)
        self.assertEqual("c1", results[0].chunk_id)
        self.assertEqual("doc-1", results[0].doc_id)
        self.assertEqual("p1", results[0].parent_id)
        self.assertEqual(3.14, results[0].score)
        self.assertEqual("CLI/Flags", results[0].title_path)

    def test_search_applies_doc_id_filter(self):
        store = FakeMilvusStore()
        store.bm25_hits = [
            {"metadata": {"chunk_id": "c1", "doc_id": "doc-1", "parent_id": "p1"}, "bm25_score": 1.0},
            {"metadata": {"chunk_id": "c2", "doc_id": "doc-2", "parent_id": "p2"}, "bm25_score": 1.0},
        ]
        keyword_search = MilvusKeywordSearch(store)

        results = keyword_search.search("timeout", top_k=5, filters={"doc_ids": ["doc-2"]})

        self.assertEqual(["c2"], [result.chunk_id for result in results])

    def test_delete_by_doc_id_delegates_to_milvus_store(self):
        store = FakeMilvusStore()
        keyword_search = MilvusKeywordSearch(store)

        keyword_search.delete_by_doc_id("doc-1")

        self.assertEqual(["doc-1"], store.deleted)

    def test_sqlite_fts_search_returns_traceable_exact_term_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            repo.upsert_document("doc-1", "manual.md", "md", "manual.md", "parsed")
            repo.replace_chunks(
                "doc-1",
                [
                    Chunk("p1", "doc-1", None, "parent", "CLI", "parent text", "parent text", 1, 1, 3, {"source": "manual.md"}),
                    Chunk("c1", "doc-1", "p1", "child", "CLI/Flags", "Use --timeout with ERR_CODE_42", "Use --timeout with ERR_CODE_42", 7, 7, 5, {"source": "manual.md"}),
                ],
            )
            repo.upsert_document("doc-2", "other.md", "md", "other.md", "parsed")
            repo.replace_chunks(
                "doc-2",
                [Chunk("c2", "doc-2", "p2", "child", "CLI/Flags", "Use CONFIG_KEY only", "Use CONFIG_KEY only", 8, 8, 5, {"source": "other.md"})],
            )
            keyword_search = SQLiteFTSKeywordSearch(repo)

            results = keyword_search.search("ERR_CODE_42 --timeout", top_k=5, filters={"doc_ids": ["doc-1"]})

        self.assertEqual(1, len(results))
        self.assertEqual("c1", results[0].chunk_id)
        self.assertEqual("doc-1", results[0].doc_id)
        self.assertEqual("p1", results[0].parent_id)
        self.assertEqual("child", results[0].chunk_type)
        self.assertEqual("CLI/Flags", results[0].title_path)
        self.assertEqual(7, results[0].page_start)
        self.assertGreater(results[0].score, 0)

    def test_sqlite_fts_delete_by_doc_id_removes_keyword_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DocumentRepository(Path(tmp) / "rag.sqlite3")
            repo.upsert_document("doc-1", "manual.md", "md", "manual.md", "parsed")
            repo.replace_chunks(
                "doc-1",
                [Chunk("c1", "doc-1", "p1", "child", "CLI", "ERR_CODE_42", "ERR_CODE_42", 1, 1, 3, {})],
            )
            keyword_search = SQLiteFTSKeywordSearch(repo)

            keyword_search.delete_by_doc_id("doc-1")

            self.assertEqual([], keyword_search.search("ERR_CODE_42", top_k=5))


if __name__ == "__main__":
    unittest.main()
