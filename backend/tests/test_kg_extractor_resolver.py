import unittest
from types import SimpleNamespace

from app.models.kg_models import Entity
from app.services.agent_prompt_templates import PromptTemplateCatalog
from app.services.entity_resolver import BaselineEntityResolver, stable_entity_id
from app.services.kg_extractor import OpenAIKGExtractor, parse_kg_extraction_payload


class FakeVectorProvider:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.queries = []

    def search_similar(self, entity, top_k=3):
        self.queries.append(entity)
        return self.matches[:top_k]


class FakeChatCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class KGExtractorResolverTests(unittest.TestCase):
    def test_parse_kg_extraction_payload_validates_entities_and_relations(self):
        result = parse_kg_extraction_payload(
            {
                "entities": [
                    {
                        "name": "Redis",
                        "type": "Middleware",
                        "description": "Cache middleware",
                        "aliases": ["redis-server"],
                        "confidence": 0.9,
                        "evidence": "Redis is used as cache.",
                    }
                ],
                "relations": [
                    {
                        "source": "Service A",
                        "target": "Redis",
                        "relation": "DEPENDS_ON",
                        "description": "Service A depends on Redis",
                        "confidence": 0.8,
                        "evidence": "Service A depends on Redis.",
                    }
                ],
            },
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_id="parent-1",
            page_start=4,
            page_end=5,
            extractor_version="kg-v1",
        )

        self.assertEqual("Redis", result.entities[0].name)
        self.assertEqual("DEPENDS_ON", result.relations[0].relation_type)
        self.assertEqual("parent-1", result.relations[0].source_chunk_id)
        self.assertEqual("doc-1", result.relations[0].doc_id)
        self.assertEqual(4, result.relations[0].page_start)

    def test_parse_kg_extraction_payload_rejects_invalid_relation_type(self):
        with self.assertRaises(ValueError):
            parse_kg_extraction_payload(
                {"entities": [], "relations": [{"source": "A", "target": "B", "relation": "BROKE"}]},
                doc_id="doc-1",
                parent_id="parent-1",
                chunk_id="parent-1",
                page_start=None,
                page_end=None,
                extractor_version="kg-v1",
            )

    def test_openai_extractor_accepts_parent_chunk_and_parses_json(self):
        completion = FakeChatCompletions(
            '{"entities":[{"name":"Redis","type":"Middleware"}],"relations":[]}'
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=completion))
        extractor = OpenAIKGExtractor(client=client, model="test-model", extractor_version="kg-v1")

        result = extractor.extract(
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_id="parent-1",
            title_path="Architecture",
            content="Service A uses Redis",
            page_start=1,
            page_end=1,
        )

        self.assertEqual("Redis", result.entities[0].name)
        self.assertEqual("test-model", completion.calls[0]["model"])
        self.assertIn("Service A uses Redis", completion.calls[0]["messages"][1]["content"])

    def test_resolver_matches_exact_alias_vector_and_creates_new_ids(self):
        existing = Entity(
            id="entity-redis",
            type="Middleware",
            name="Redis",
            aliases=["redis-server"],
            description="Cache",
        )
        vector = FakeVectorProvider(matches=[{"entity": existing, "score": 0.92}])
        resolver = BaselineEntityResolver(existing_entities=[existing], entity_vector_provider=vector, similarity_threshold=0.9)

        exact = resolver.resolve(Entity(id="", type="Middleware", name="redis"))
        alias = resolver.resolve(Entity(id="", type="Middleware", name="redis-server"))
        vector_match = resolver.resolve(Entity(id="", type="Middleware", name="Redis cache"))
        created = resolver.resolve(Entity(id="", type="Service", name="Billing API"))

        self.assertEqual("entity-redis", exact.id)
        self.assertEqual("entity-redis", alias.id)
        self.assertEqual("entity-redis", vector_match.id)
        self.assertEqual(stable_entity_id("Service", "Billing API"), created.id)

    def test_openai_extractor_can_render_graph_prompt_template(self):
        completion = FakeChatCompletions(
            '{"entities":[{"name":"Redis","type":"Middleware"}],"relations":[]}'
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=completion))
        catalog = PromptTemplateCatalog.load_directory("config/prompt_templates", required_ids={"graph_extraction"})
        extractor = OpenAIKGExtractor(client=client, model="test-model", prompt_catalog=catalog)

        extractor.extract(
            doc_id="doc-1",
            parent_id="parent-1",
            chunk_id="parent-1",
            title_path="Architecture",
            content="Service A uses Redis",
            page_start=1,
            page_end=1,
        )

        prompt = completion.calls[0]["messages"][1]["content"]
        self.assertIn("Extract a knowledge graph", prompt)
        self.assertIn("Service A uses Redis", prompt)


if __name__ == "__main__":
    unittest.main()
