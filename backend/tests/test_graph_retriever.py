import unittest

from app.models.kg_models import Entity, GraphPath, Relation
from app.models.graph_retrieval import GraphRetrievalResult
from app.services.kg.graph_retriever import GraphRetriever


class FakeEvidenceRepository:
    def __init__(self):
        self.chunks = {
            "chunk-1": {
                "id": "chunk-1",
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "chunk_type": "parent",
                "title_path": "Architecture",
                "content": "Service A depends on Redis.",
                "page_start": 1,
                "page_end": 1,
                "metadata_json": {"source": "manual.md"},
            }
        }

    def get_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)


class FakeEntityVectorProvider:
    def __init__(self):
        self.calls = []

    def search_similar(self, entity, top_k=3):
        self.calls.append((entity, top_k))
        return [
            {
                "entity": Entity(id="entity-redis", type="Middleware", name="Redis", aliases=["redis-server"]),
                "score": 0.95,
            }
        ]


class FakeGraphProvider:
    def __init__(self):
        self.search_calls = []
        self.neighbor_calls = []
        self.path_calls = []
        self.entities = [
            {"entity": Entity(id="entity-service-a", type="Service", name="Service A"), "score": 0.9},
            {"entity": Entity(id="entity-redis", type="Middleware", name="Redis", aliases=["redis-server"]), "score": 0.88},
        ]
        self.valid_relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            description="Service A depends on Redis",
            confidence=0.8,
            source_chunk_id="chunk-1",
            doc_id="doc-1",
            page_start=1,
            page_end=1,
            extractor_version="kg-v1",
            created_at="2026-07-07T00:00:00",
        )

    def search_entities(self, query, limit=10, entity_types=None):
        self.search_calls.append({"query": query, "limit": limit, "entity_types": entity_types})
        lowered = query.lower()
        return [item for item in self.entities if item["entity"].name.lower() in lowered or query.lower() in item["entity"].name.lower()]

    def get_neighbors(self, entity_id, depth=1, limit=20):
        self.neighbor_calls.append({"entity_id": entity_id, "depth": depth, "limit": limit})
        return {
            "entities": [item["entity"] for item in self.entities],
            "relations": [
                self.valid_relation,
                {
                    "source_entity_id": "entity-service-a",
                    "target_entity_id": "entity-redis",
                    "relation_type": "NOT_ALLOWED",
                    "source_chunk_id": "chunk-1",
                    "doc_id": "doc-1",
                    "extractor_version": "kg-v1",
                },
                {
                    "source_entity_id": "entity-service-a",
                    "target_entity_id": "entity-redis",
                    "relation_type": "DEPENDS_ON",
                    "source_chunk_id": "missing-chunk",
                    "doc_id": "doc-1",
                    "extractor_version": "kg-v1",
                },
            ],
        }

    def find_paths(self, source_entity_id, target_entity_id, max_depth=3, limit=10):
        self.path_calls.append(
            {
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "max_depth": max_depth,
                "limit": limit,
            }
        )
        valid_path = GraphPath(
            entities=[item["entity"] for item in self.entities],
            relations=[self.valid_relation],
            source_chunk_ids=["chunk-1"],
            confidence=0.8,
        )
        missing_chunk_relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            confidence=0.8,
            source_chunk_id="missing-chunk",
            doc_id="doc-1",
            extractor_version="kg-v1",
        )
        invalid_path = GraphPath(
            entities=[item["entity"] for item in self.entities],
            relations=[missing_chunk_relation],
            source_chunk_ids=["missing-chunk"],
            confidence=0.8,
        )
        return [valid_path, invalid_path]


class GraphRetrieverTests(unittest.TestCase):
    def make_retriever(self, graph=None, evidence=None, vector=None):
        return GraphRetriever(
            graph_provider=graph or FakeGraphProvider(),
            evidence_repository=evidence or FakeEvidenceRepository(),
            entity_vector_provider=vector,
            max_neighbor_depth=2,
            max_path_depth=3,
            entity_limit=5,
            relation_limit=10,
            path_limit=5,
        )

    def test_graph_retrieval_result_preserves_traceable_fields(self):
        entity = Entity(id="entity-redis", type="Middleware", name="Redis")
        relation = Relation(
            source_entity_id="entity-service-a",
            target_entity_id="entity-redis",
            relation_type="DEPENDS_ON",
            source_chunk_id="chunk-1",
            doc_id="doc-1",
            extractor_version="kg-v1",
        )
        result = GraphRetrievalResult(
            entities=[entity],
            relations=[relation],
            paths=[GraphPath(entities=[entity], relations=[relation], source_chunk_ids=["chunk-1"], confidence=0.8)],
            source_chunk_ids=["chunk-1"],
            confidence=0.8,
            evidence_chunks=[{"id": "chunk-1"}],
            debug_info={"source": "test"},
        )

        self.assertEqual(["chunk-1"], result.source_chunk_ids)
        self.assertEqual("Redis", result.entities[0].name)
        self.assertEqual("test", result.debug_info["source"])

    def test_entity_search_uses_graph_and_optional_vector_results(self):
        graph = FakeGraphProvider()
        vector = FakeEntityVectorProvider()
        retriever = self.make_retriever(graph=graph, vector=vector)

        result = retriever.entity_search("Redis cache")

        self.assertEqual(["Redis"], [entity.name for entity in result.entities])
        self.assertEqual("Redis cache", graph.search_calls[0]["query"])
        self.assertEqual("Redis cache", vector.calls[0][0].name)
        self.assertGreaterEqual(result.confidence, 0.95)

    def test_neighbor_search_caps_depth_filters_invalid_relations_and_validates_sources(self):
        graph = FakeGraphProvider()
        retriever = self.make_retriever(graph=graph)

        result = retriever.neighbor_search("entity-service-a", depth=99)

        self.assertEqual(2, graph.neighbor_calls[0]["depth"])
        self.assertEqual(["DEPENDS_ON"], [relation.relation_type for relation in result.relations])
        self.assertEqual(["chunk-1"], result.source_chunk_ids)
        self.assertEqual(["chunk-1"], [chunk["id"] for chunk in result.evidence_chunks])
        self.assertEqual(2, len(result.debug_info["excluded_relations"]))

    def test_path_search_resolves_names_filters_missing_chunks_and_returns_paths(self):
        graph = FakeGraphProvider()
        retriever = self.make_retriever(graph=graph)

        result = retriever.path_search("Service A", "Redis", max_depth=9)

        self.assertEqual(3, graph.path_calls[0]["max_depth"])
        self.assertEqual("entity-service-a", graph.path_calls[0]["source_entity_id"])
        self.assertEqual("entity-redis", graph.path_calls[0]["target_entity_id"])
        self.assertEqual(1, len(result.paths))
        self.assertEqual(["chunk-1"], result.source_chunk_ids)
        self.assertEqual(1, len(result.debug_info["excluded_paths"]))

    def test_graph_context_build_returns_structured_context_without_answer(self):
        graph = FakeGraphProvider()
        retriever = self.make_retriever(graph=graph)
        path_result = retriever.path_search("Service A", "Redis", max_depth=3)

        context = retriever.graph_context_build(paths=path_result.paths, entities=path_result.entities)

        self.assertFalse(hasattr(context, "answer"))
        self.assertIn("Service A -[DEPENDS_ON]-> Redis", context.path_descriptions[0])
        self.assertEqual(["chunk-1"], context.source_chunk_ids)
        self.assertEqual(["chunk-1"], [chunk["id"] for chunk in context.evidence_chunks])


if __name__ == "__main__":
    unittest.main()
