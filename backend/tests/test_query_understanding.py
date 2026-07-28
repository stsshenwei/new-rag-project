import json
import unittest

from app.services.query_understanding import (
    OpenAIQueryIntentClient,
    OpenAIQueryRewriteClient,
    QueryUnderstandingConfig,
    QueryUnderstandingResult,
    QueryUnderstandingService,
)
from app.services.agent_prompt_templates import PromptTemplateCatalog


class FakeRewriteClient:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def rewrite(self, query, understanding):
        self.calls.append((query, understanding.normalized_query))
        return self.output


class FakeIntentClient:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def detect(self, query, understanding, *, conversation_context="", language="zh-CN"):
        self.calls.append(
            {
                "query": query,
                "normalized_query": understanding.normalized_query,
                "conversation_context": conversation_context,
                "language": language,
            }
        )
        return self.output


class QueryUnderstandingTests(unittest.TestCase):
    def test_enabled_understanding_does_not_add_domain_specific_queries_without_llm_rewrite(self):
        service = QueryUnderstandingService(config=QueryUnderstandingConfig(enabled=True, max_queries=5))

        result = service.understand("我现在需要一个能接28个分光器的OLT帮我选一款")

        self.assertEqual(["我现在需要一个能接28个分光器的OLT帮我选一款"], result.retrieval_queries)
        self.assertEqual([], result.expanded_terms)
        self.assertEqual([], result.applied_terms)

    def test_result_has_defaults_and_serializes(self):
        service = QueryUnderstandingService(config=QueryUnderstandingConfig(enabled=False))

        result = service.understand("8个电口")

        self.assertEqual("8个电口", result.original_query)
        self.assertEqual("8个电口", result.normalized_query)
        self.assertEqual("fallback", result.source)
        self.assertEqual(["8个电口"], result.retrieval_queries)
        serialized = result.to_dict()
        self.assertEqual("8个电口", serialized["original_query"])
        json.dumps(serialized, ensure_ascii=False)

    def test_disabled_understanding_uses_raw_query(self):
        service = QueryUnderstandingService(config=QueryUnderstandingConfig(enabled=False, max_queries=5))

        result = service.understand("8个电口")

        self.assertEqual("8个电口", result.normalized_query)
        self.assertEqual(["8个电口"], result.retrieval_queries)
        self.assertEqual([], result.applied_terms)

    def test_llm_retrieval_queries_are_deduplicated_and_capped(self):
        service = QueryUnderstandingService(
            rewrite_client=FakeRewriteClient({"queries": ["variant-a", "variant-a", "variant-b", "variant-c"]}),
            config=QueryUnderstandingConfig(enabled=True, rewrite_enabled=True, max_queries=3),
        )

        result = service.understand("original")

        self.assertEqual(len(result.retrieval_queries), len(set(result.retrieval_queries)))
        self.assertEqual(3, len(result.retrieval_queries))

    def test_llm_rewrite_adds_valid_queries(self):
        rewrite_client = FakeRewriteClient({"queries": ["8个RJ45交换机", "8口以太网接口"]})
        service = QueryUnderstandingService(
            rewrite_client=rewrite_client,
            config=QueryUnderstandingConfig(enabled=True, rewrite_enabled=True, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertEqual(1, len(rewrite_client.calls))
        self.assertIn("8个RJ45交换机", result.retrieval_queries)
        self.assertEqual([], result.expanded_terms)
        self.assertEqual("llm", result.source)

    def test_invalid_llm_rewrite_is_ignored(self):
        rewrite_client = FakeRewriteClient("not-json")
        service = QueryUnderstandingService(
            rewrite_client=rewrite_client,
            config=QueryUnderstandingConfig(enabled=True, rewrite_enabled=True, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertNotIn("not-json", result.retrieval_queries)
        self.assertEqual(["8个电口"], result.retrieval_queries)


    def test_prompt_backed_intent_detection_updates_result(self):
        intent_client = FakeIntentClient(
            {
                "intent": "comparison",
                "constraints": [{"field": "ports", "operator": ">=", "value": 8}],
                "needs_graph": False,
            }
        )
        service = QueryUnderstandingService(
            config=QueryUnderstandingConfig(
                enabled=True,
                intent_detection_enabled=True,
                max_queries=3,
                language="zh-CN",
            ),
            intent_client=intent_client,
        )

        result = service.understand("compare two OLT devices")

        self.assertEqual("comparison", result.intent)
        self.assertEqual([{"field": "ports", "operator": ">=", "value": 8}], result.constraints)
        self.assertEqual("llm", result.source)
        self.assertEqual(1, len(intent_client.calls))
        self.assertEqual("zh-CN", intent_client.calls[0]["language"])

    def test_invalid_intent_detection_is_ignored(self):
        service = QueryUnderstandingService(
            config=QueryUnderstandingConfig(enabled=True, intent_detection_enabled=True),
            intent_client=FakeIntentClient("not-json"),
        )

        result = service.understand("plain query")

        self.assertEqual("technical_document_search", result.intent)
        self.assertEqual([], result.constraints)
        self.assertEqual("fallback", result.source)

    def test_openai_rewrite_client_uses_prompt_catalog(self):
        class FakeCompletions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                from types import SimpleNamespace

                self.calls.append(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"queries":["GPON OLT"]}'))])

        completions = FakeCompletions()
        client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
        catalog = PromptTemplateCatalog.load_directory("config/prompt_templates", required_ids={"query_rewrite"})
        rewrite_client = OpenAIQueryRewriteClient(client, "model", prompt_catalog=catalog)
        understanding = QueryUnderstandingResult(
            original_query="GPON",
            normalized_query="GPON",
            expanded_terms=[],
            retrieval_queries=["GPON"],
        )

        output = rewrite_client.rewrite("GPON", understanding)

        self.assertEqual('{"queries":["GPON OLT"]}', output)
        self.assertIn("Original query: GPON", completions.calls[0]["messages"][0]["content"])

    def test_openai_intent_client_uses_prompt_catalog(self):
        class FakeCompletions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                from types import SimpleNamespace

                self.calls.append(kwargs)
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content='{"intent":"fact","constraints":[]}')
                        )
                    ]
                )

        completions = FakeCompletions()
        client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
        catalog = PromptTemplateCatalog.load_directory("config/prompt_templates", required_ids={"intent_detection"})
        intent_client = OpenAIQueryIntentClient(client, "model", prompt_catalog=catalog)
        understanding = QueryUnderstandingResult(
            original_query="GPON",
            normalized_query="GPON",
            retrieval_queries=["GPON"],
        )

        output = intent_client.detect("GPON", understanding, conversation_context="history", language="zh-CN")

        self.assertEqual('{"intent":"fact","constraints":[]}', output)
        system_content = completions.calls[0]["messages"][0]["content"]
        self.assertIn("User query:", system_content)
        self.assertIn("GPON", system_content)
        self.assertIn("history", system_content)


if __name__ == "__main__":
    unittest.main()
