import unittest
from unittest.mock import patch

from app.models.document_models import Chunk
from app.models.knowledge_base import KnowledgeBaseScope
from app.models.processing_config import PROCESSING_VERSION
from app.services.retrieval.vector_store import MilvusSchemaResetRequired, MilvusVectorStore, _create_or_load_collection


class FakeProvider:
    def embed_text(self, text):
        return [0.1, 0.2]

    def embed_batch(self, texts):
        return [[float(i), 0.2] for i, _ in enumerate(texts)]


class MilvusVectorStoreTests(unittest.TestCase):
    def test_collection_factory_adds_bm25_schema_when_enabled(self):
        created = {}

        class FakeCollection:
            def __init__(self, name, schema):
                created["name"] = name
                created["schema"] = schema

            def create_index(self, field_name, index_params):
                created.setdefault("indexes", []).append((field_name, index_params))

            def load(self):
                pass

        with patch("pymilvus.connections.connect"):
            with patch("pymilvus.utility.has_collection", return_value=False):
                with patch("pymilvus.Collection", side_effect=FakeCollection):
                    _create_or_load_collection("fake", "root:Milvus", "rag_chunk_vectors", 2, bm25_enabled=True)

        field_names = [field.name for field in created["schema"].fields]
        function_names = [function.name for function in created["schema"].functions]

        self.assertIn("bm25_text", field_names)
        self.assertIn("bm25_sparse", field_names)
        self.assertIn("workspace_id", field_names)
        self.assertIn("knowledge_base_id", field_names)
        self.assertIn("strategy", field_names)
        self.assertIn("processing_version", field_names)
        self.assertIn("size_unit", field_names)
        self.assertIn("image_id", field_names)
        self.assertIn("storage_key", field_names)
        self.assertIn("source_type", field_names)
        self.assertIn("bm25_function", function_names)
        self.assertIn(("bm25_sparse", {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25", "params": {}}), created["indexes"])

    def test_collection_factory_rejects_existing_collection_without_bm25_schema_when_enabled(self):
        class FakeField:
            def __init__(self, name):
                self.name = name

        class FakeSchema:
            fields = [FakeField("id"), FakeField("embedding"), FakeField("chunk_id")]

        class FakeCollection:
            schema = FakeSchema()

            def __init__(self, name):
                self.name = name

            def load(self):
                pass

        with patch("pymilvus.connections.connect"):
            with patch("pymilvus.utility.has_collection", return_value=True):
                with patch("pymilvus.Collection", side_effect=FakeCollection):
                    with self.assertRaisesRegex(RuntimeError, "clean-rebuild"):
                        _create_or_load_collection("fake", "root:Milvus", "rag_chunk_vectors", 2, bm25_enabled=True)

    def test_vector_store_passes_token_to_collection_factory(self):
        class FakeCollection:
            pass

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()) as factory:
            MilvusVectorStore(
                uri="http://127.0.0.1:19530",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
            )

        factory.assert_called_once_with("http://127.0.0.1:19530", "root:Milvus", "rag_chunk_vectors", 2, bm25_enabled=False)

    def test_vector_store_indexes_child_table_ocr_and_image_chunks(self):
        inserted = []

        class FakeCollection:
            def insert(self, rows):
                inserted.extend(rows)

            def flush(self):
                pass

            def num_entities(self):
                return len(inserted)

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
            )
            chunks = [
                Chunk("p1", "doc-1", None, "parent", "章", "parent", "parent", 1, 1, 1, {}),
                Chunk("c1", "doc-1", "p1", "child", "章", "child", "child", 1, 1, 1, {"strategy": "heading"}),
                Chunk("t1", "doc-1", "p1", "table", "章", "table", "| A |", 1, 1, 1, {"fields": ["A"]}),
                Chunk(
                    "img1",
                    "doc-1",
                    "p1",
                    "image_ocr",
                    "章",
                    "image text",
                    "image text",
                    2,
                    2,
                    2,
                    {
                        "strategy": "image_ocr",
                        "image_id": "page-2-image-1",
                        "storage_key": "media/page-2-image-1.jpg",
                        "source_type": "scanned_page",
                    },
                ),
            ]

            store.upsert_chunks(chunks)

        ocr_chunk = Chunk("o1", "doc-1", "p1", "ocr", "Title", "OCR text", "OCR text", 1, 1, 1, {"source": "docling_ocr"})
        store.upsert_chunks([ocr_chunk])

        self.assertEqual(4, len(inserted))
        self.assertEqual({"child", "table", "ocr", "image_ocr"}, {row["chunk_type"] for row in inserted})
        child = next(row for row in inserted if row["chunk_id"] == "c1")
        image = next(row for row in inserted if row["chunk_id"] == "img1")
        self.assertEqual("heading", child["strategy"])
        self.assertEqual(PROCESSING_VERSION, image["processing_version"])
        self.assertEqual("chars", image["size_unit"])
        self.assertEqual("page-2-image-1", image["image_id"])
        self.assertEqual("media/page-2-image-1.jpg", image["storage_key"])
        self.assertEqual("scanned_page", image["source_type"])

    def test_vector_store_indexes_bm25_text_when_enabled(self):
        inserted = []

        class FakeCollection:
            def insert(self, rows):
                inserted.extend(rows)

            def flush(self):
                pass

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
                bm25_enabled=True,
            )
            store.upsert_chunks(
                [
                    Chunk("c1", "doc-1", "p1", "child", "Title", "body", "body", 1, 1, 1, {"source": "a.md"}),
                ]
            )

        self.assertEqual("Title\nbody", inserted[0]["bm25_text"])

    def test_query_dense_delegates_to_existing_vector_query(self):
        class FakeCollection:
            def search(self, **kwargs):
                return [[]]

            def num_entities(self):
                return 1

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
            )

            self.assertEqual([], store.query_dense("test", top_k=3))
            self.assertEqual([], store.search_dense("test", top_k=3))

    def test_query_bm25_returns_empty_when_disabled(self):
        class FakeCollection:
            def num_entities(self):
                return 1

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
                bm25_enabled=False,
            )

            self.assertEqual([], store.query_bm25("exact term", top_k=3))
            self.assertEqual([], store.search_bm25("exact term", top_k=3))

    def test_query_bm25_searches_sparse_field_when_enabled(self):
        calls = []

        class FakeEntity:
            def __init__(self, fields):
                self.fields = fields

            def get(self, field):
                return self.fields.get(field, "")

        class FakeHit:
            score = 0.82
            entity = FakeEntity(
                {
                    "chunk_id": "c1",
                    "doc_id": "doc-1",
                    "parent_id": "p1",
                    "chunk_type": "child",
                    "strategy": "heading",
                    "processing_version": "weknora-adaptive-v1",
                    "size_unit": "chars",
                    "image_id": "",
                    "storage_key": "",
                    "source_type": "",
                    "title_path": "Title",
                    "page_start": 1,
                    "page_end": 2,
                }
            )

        class FakeCollection:
            def search(self, **kwargs):
                calls.append(kwargs)
                return [[FakeHit()]]

            def num_entities(self):
                return 1

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
                bm25_enabled=True,
            )
            hits = store.query_bm25("exact term", top_k=3)

        self.assertEqual("bm25_sparse", calls[0]["anns_field"])
        self.assertIn('knowledge_base_id in ["default-knowledge-base"]', calls[0]["expr"])
        self.assertEqual(["exact term"], calls[0]["data"])
        self.assertEqual({"metric_type": "BM25", "params": {}}, calls[0]["param"])
        self.assertEqual("c1", hits[0]["metadata"]["chunk_id"])
        self.assertEqual("doc-1", hits[0]["metadata"]["doc_id"])
        self.assertEqual("p1", hits[0]["metadata"]["parent_id"])
        self.assertIn("processing_version", calls[0]["output_fields"])
        self.assertEqual("heading", hits[0]["metadata"]["strategy"])
        self.assertEqual("weknora-adaptive-v1", hits[0]["metadata"]["processing_version"])
        self.assertEqual("chars", hits[0]["metadata"]["size_unit"])
        self.assertEqual(0.82, hits[0]["bm25_score"])

    def test_delete_document_deletes_matching_doc_id(self):
        deleted = []

        class FakeCollection:
            def delete(self, expr):
                deleted.append(expr)

            def flush(self):
                pass

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
            )

            store.delete_document("doc-1")

        self.assertEqual(
            ['doc_id == "doc-1" and workspace_id == "default-workspace" and knowledge_base_id in ["default-knowledge-base"]'],
            deleted,
        )

    def test_replace_document_chunks_deletes_existing_records_before_upsert(self):
        calls = []
        inserted = []

        class FakeCollection:
            def delete(self, expr):
                calls.append(("delete", expr))

            def insert(self, rows):
                calls.append(("insert", len(rows)))
                inserted.extend(rows)

            def flush(self):
                calls.append(("flush", None))

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore(
                uri="fake",
                token="root:Milvus",
                collection_name="rag_chunk_vectors",
                embedding_dim=2,
                embedding_provider=FakeProvider(),
            )

            store.replace_document_chunks(
                "doc-1",
                [
                    Chunk("c1", "doc-1", "p1", "child", "Title", "body", "body", 1, 1, 1, {}),
                ],
            )

        self.assertEqual(
            (
                "delete",
                'doc_id == "doc-1" and workspace_id == "default-workspace" and knowledge_base_id in ["default-knowledge-base"]',
            ),
            calls[0],
        )
        self.assertIn(("insert", 1), calls)
        self.assertEqual("doc-1", inserted[0]["doc_id"])

    def test_dense_and_bm25_queries_apply_explicit_multi_kb_and_document_scope_before_recall(self):
        calls = []

        class FakeCollection:
            def search(self, **kwargs):
                calls.append(kwargs)
                return [[]]

            def num_entities(self):
                return 1

        with patch("app.services.retrieval.vector_store._create_or_load_collection", return_value=FakeCollection()):
            store = MilvusVectorStore("fake", "", "rag_chunk_vectors", 2, FakeProvider(), bm25_enabled=True)
            scope = KnowledgeBaseScope("ws-1", ("kb-1", "kb-2"), document_ids=("doc-1", "doc-2"))
            store.query_dense("query", 5, scope=scope)
            store.query_bm25("query", 5, scope=scope)

        self.assertEqual(2, len(calls))
        self.assertEqual(
            'workspace_id == "ws-1" and knowledge_base_id in ["kb-1", "kb-2"] and doc_id in ["doc-1", "doc-2"]',
            calls[0]["expr"],
        )
        self.assertEqual(calls[0]["expr"], calls[1]["expr"])

    def test_incompatible_collection_exposes_reset_required_and_refuses_reads_and_writes(self):
        with patch(
            "app.services.retrieval.vector_store._create_or_load_collection",
            side_effect=MilvusSchemaResetRequired("requires reset"),
        ):
            store = MilvusVectorStore("fake", "", "rag_chunk_vectors", 2, FakeProvider())

        self.assertTrue(store.reset_required)
        with self.assertRaises(MilvusSchemaResetRequired):
            store.query_dense("query", 3)
        with self.assertRaises(MilvusSchemaResetRequired):
            store.upsert_chunks([Chunk("c", "d", "p", "child", "", "x", "x", 1, 1, 1, {})])


if __name__ == "__main__":
    unittest.main()
