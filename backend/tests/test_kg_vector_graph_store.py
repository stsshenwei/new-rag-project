import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.models.kg_models import Entity, GraphPath, Relation
from app.services.entity_vector_store import MilvusEntityVectorStore, _validate_entity_collection_schema
from app.services.graph_store import Neo4jGraphStore


class FakeEmbeddingProvider:
    def embed_batch(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_text(self, text):
        return [0.1, 0.2, 0.3]


class FakeCollection:
    def __init__(self):
        self.rows = []
        self.search_calls = []
        self.flushed = False

    def insert(self, rows):
        self.rows.extend(rows)

    def flush(self):
        self.flushed = True

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        hit = SimpleNamespace(
            score=0.93,
            entity={
                "entity_id": "entity-redis",
                "entity_type": "Middleware",
                "entity_name": "Redis",
                "description": "Cache",
                "aliases": '["redis-server"]',
                "metadata": "{}",
            },
        )
        return [[hit]]


class FakeSession:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **params):
        self.calls.append((query, params))


class FakeDriver:
    def __init__(self):
        self.calls = []

    def session(self):
        return FakeSession(self.calls)

    def close(self):
        self.closed = True


class FakeReadSession:
    def __init__(self, calls, rows):
        self.calls = calls
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **params):
        self.calls.append((query, params))
        return self.rows


class FakeReadDriver:
    def __init__(self, rows):
        self.calls = []
        self.rows = rows

    def session(self):
        return FakeReadSession(self.calls, self.rows)


class KGVectorGraphStoreTests(unittest.TestCase):
    def test_entity_vector_store_upserts_and_searches_entities(self):
        collection = FakeCollection()
        store = MilvusEntityVectorStore(
            uri="memory",
            token="",
            collection_name="kg_entity_vectors",
            embedding_dim=3,
            embedding_provider=FakeEmbeddingProvider(),
            collection=collection,
        )
        entity = Entity(
            id="entity-redis",
            type="Middleware",
            name="Redis",
            description="Cache",
            aliases=["redis-server"],
            metadata={"tenant_id": "tenant-1", "knowledge_base_id": "kb-1"},
        )

        store.upsert_entities([entity])
        matches = store.search_similar(Entity(id="", type="Middleware", name="Redis cache"), top_k=3)

        self.assertEqual("entity-redis", collection.rows[0]["entity_id"])
        self.assertEqual("tenant-1", collection.rows[0]["tenant_id"])
        self.assertEqual("kg_entity_vectors", store.collection_name)
        self.assertEqual("entity-redis", matches[0]["entity"].id)
        self.assertEqual(0.93, matches[0]["score"])

    def test_entity_collection_schema_validation_reports_missing_fields(self):
        field = lambda name: SimpleNamespace(name=name)
        collection = SimpleNamespace(schema=SimpleNamespace(fields=[field("id"), field("dense_vector")]))

        with self.assertRaises(RuntimeError):
            _validate_entity_collection_schema(collection, "kg_entity_vectors")

    def test_neo4j_graph_store_import_is_lazy(self):
        sys.modules.pop("neo4j", None)
        import app.services.graph_store as graph_store

        self.assertFalse(hasattr(graph_store, "GraphDatabase"))

    def test_neo4j_graph_store_writes_entity_and_evidence_bound_relation(self):
        driver = FakeDriver()
        store = Neo4jGraphStore(uri="bolt://test", auth=("u", "p"), driver_factory=lambda uri, auth: driver)
        entity = Entity(id="entity-redis", type="Middleware", name="Redis", aliases=["redis-server"], description="Cache")
        relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            description="Service A depends on Redis",
            confidence=0.8,
            source_chunk_id="parent-1",
            doc_id="doc-1",
            page_start=2,
            extractor_version="kg-v1",
            created_at="2026-07-06T12:00:00",
        )

        store.upsert_entity(entity)
        store.upsert_relation(relation)

        queries = [call[0] for call in driver.calls]
        relation_params = driver.calls[1][1]
        self.assertIn("MERGE (e:Entity:Middleware", queries[0])
        self.assertIn("DEPENDS_ON", queries[1])
        self.assertEqual("parent-1", relation_params["source_chunk_id"])
        self.assertEqual("doc-1", relation_params["doc_id"])

    def test_neo4j_missing_driver_raises_clear_runtime_error(self):
        with patch.dict(sys.modules, {"neo4j": None}):
            with self.assertRaises(RuntimeError):
                Neo4jGraphStore(uri="bolt://test", auth=("u", "p"))

    def test_neo4j_graph_store_searches_entities_by_name_and_alias(self):
        driver = FakeReadDriver(
            [
                {
                    "entity": {
                        "id": "entity-redis",
                        "entity_type": "Middleware",
                        "name": "Redis",
                        "description": "Cache",
                        "aliases": ["redis-server"],
                        "confidence": 0.9,
                        "metadata": {"source": "kg"},
                    },
                    "score": 0.9,
                }
            ]
        )
        store = Neo4jGraphStore(uri="bolt://test", auth=("u", "p"), driver_factory=lambda uri, auth: driver)

        results = store.search_entities("redis-server", limit=5)

        query, params = driver.calls[0]
        self.assertIn("MATCH (e:Entity)", query)
        self.assertIn("toLower(e.name)", query)
        self.assertIn("aliases", query)
        self.assertEqual("redis-server", params["search_text"])
        self.assertEqual(5, params["limit"])
        self.assertEqual("entity-redis", results[0]["entity"].id)
        self.assertEqual(0.9, results[0]["score"])

    def test_neo4j_graph_store_returns_neighbors_with_evidence_bound_relations(self):
        driver = FakeReadDriver(
            [
                {
                    "entities": [
                        {"id": "entity-service-a", "entity_type": "Service", "name": "Service A"},
                        {"id": "entity-redis", "entity_type": "Middleware", "name": "Redis"},
                    ],
                    "relations": [
                        {
                            "source_entity_id": "entity-service-a",
                            "target_entity_id": "entity-redis",
                            "relation_type": "DEPENDS_ON",
                            "description": "Service A depends on Redis",
                            "confidence": 0.8,
                            "source_chunk_id": "chunk-1",
                            "doc_id": "doc-1",
                            "page_start": 1,
                            "page_end": 1,
                            "extractor_version": "kg-v1",
                            "created_at": "2026-07-07T00:00:00",
                        }
                    ],
                }
            ]
        )
        store = Neo4jGraphStore(uri="bolt://test", auth=("u", "p"), driver_factory=lambda uri, auth: driver)

        result = store.get_neighbors("entity-service-a", depth=2, limit=10)

        query, params = driver.calls[0]
        self.assertIn("*1..2", query)
        self.assertEqual("entity-service-a", params["entity_id"])
        self.assertEqual("DEPENDS_ON", result["relations"][0].relation_type)
        self.assertEqual("chunk-1", result["relations"][0].source_chunk_id)

    def test_neo4j_graph_store_returns_paths_with_evidence_bound_relations(self):
        driver = FakeReadDriver(
            [
                {
                    "entities": [
                        {"id": "entity-service-a", "entity_type": "Service", "name": "Service A"},
                        {"id": "entity-redis", "entity_type": "Middleware", "name": "Redis"},
                    ],
                    "relations": [
                        {
                            "source_entity_id": "entity-service-a",
                            "target_entity_id": "entity-redis",
                            "relation_type": "DEPENDS_ON",
                            "confidence": 0.8,
                            "source_chunk_id": "chunk-1",
                            "doc_id": "doc-1",
                            "page_start": 1,
                            "page_end": 1,
                            "extractor_version": "kg-v1",
                            "created_at": "2026-07-07T00:00:00",
                        }
                    ],
                }
            ]
        )
        store = Neo4jGraphStore(uri="bolt://test", auth=("u", "p"), driver_factory=lambda uri, auth: driver)

        paths = store.find_paths("entity-service-a", "entity-redis", max_depth=3, limit=5)

        query, params = driver.calls[0]
        self.assertIn("*1..3", query)
        self.assertEqual(5, params["limit"])
        self.assertIsInstance(paths[0], GraphPath)
        self.assertEqual(["chunk-1"], paths[0].source_chunk_ids)


if __name__ == "__main__":
    unittest.main()
