import json
import tempfile
import unittest
from pathlib import Path

from app.services.query_understanding import (
    OpenAIQueryIntentClient,
    OpenAIQueryRewriteClient,
    QueryUnderstandingConfig,
    QueryUnderstandingResult,
    QueryUnderstandingService,
    TerminologyDictionary,
    load_terminology_dictionary,
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
    def test_olt_splitter_selection_expands_capacity_and_configuration_queries(self):
        service = QueryUnderstandingService(config=QueryUnderstandingConfig(enabled=True, max_queries=5))

        result = service.understand("我现在需要一个能接28个分光器的OLT帮我选一款")

        self.assertIn("OLT 至少28个PON口 GPON接口容量", result.retrieval_queries)
        self.assertIn("32口盒式OLT GPON口", result.retrieval_queries)
        self.assertIn("OLT 业务槽位 GPON业务板卡 PON口数量", result.retrieval_queries)
        self.assertLessEqual(len(result.retrieval_queries), 5)

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

    def test_dictionary_loader_reads_terms_and_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "terms.yaml"
            path.write_text(
                """
terms:
  电口:
    canonical: RJ-45
    aliases:
      - RJ45
      - 以太网电接口
""".strip(),
                encoding="utf-8",
            )

            dictionary = load_terminology_dictionary(path)

        self.assertEqual("RJ-45", dictionary.entries["电口"].canonical)
        self.assertIn("RJ45", dictionary.entries["电口"].aliases)

    def test_dictionary_loader_missing_file_returns_empty_dictionary(self):
        dictionary = load_terminology_dictionary(Path(tempfile.mkdtemp()) / "missing.yaml")

        self.assertEqual({}, dictionary.entries)

    def test_normalizes_electric_port_to_rj45_variants(self):
        dictionary = TerminologyDictionary.from_mapping(
            {
                "电口": {
                    "canonical": "RJ-45",
                    "aliases": ["RJ45", "以太网电接口", "copper Ethernet port"],
                }
            }
        )
        service = QueryUnderstandingService(
            dictionary=dictionary,
            config=QueryUnderstandingConfig(enabled=True, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertIn("RJ-45", result.normalized_query)
        self.assertIn("RJ45", result.expanded_terms)
        self.assertIn({"term": "电口", "canonical": "RJ-45"}, result.applied_terms)
        self.assertIn("8个RJ-45", result.retrieval_queries)
        self.assertLessEqual(len(result.retrieval_queries), 5)

    def test_disabled_understanding_uses_raw_query_without_dictionary(self):
        dictionary = TerminologyDictionary.from_mapping({"电口": {"canonical": "RJ-45", "aliases": ["RJ45"]}})
        service = QueryUnderstandingService(
            dictionary=dictionary,
            config=QueryUnderstandingConfig(enabled=False, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertEqual("8个电口", result.normalized_query)
        self.assertEqual(["8个电口"], result.retrieval_queries)
        self.assertEqual([], result.applied_terms)

    def test_invalid_dictionary_entries_are_ignored(self):
        dictionary = TerminologyDictionary.from_mapping({"电口": {"aliases": ["RJ45"]}, "光口": "SFP"})
        service = QueryUnderstandingService(
            dictionary=dictionary,
            config=QueryUnderstandingConfig(enabled=True),
        )

        result = service.understand("8个电口")

        self.assertEqual("8个电口", result.normalized_query)
        self.assertEqual(["8个电口"], result.retrieval_queries)

    def test_retrieval_queries_are_deduplicated_and_capped(self):
        dictionary = TerminologyDictionary.from_mapping(
            {
                "电口": {
                    "canonical": "RJ-45",
                    "aliases": ["RJ-45", "RJ45", "以太网电接口", "copper Ethernet port"],
                }
            }
        )
        service = QueryUnderstandingService(
            dictionary=dictionary,
            config=QueryUnderstandingConfig(enabled=True, max_queries=3),
        )

        result = service.understand("8个电口")

        self.assertEqual(len(result.retrieval_queries), len(set(result.retrieval_queries)))
        self.assertEqual(3, len(result.retrieval_queries))

    def test_llm_rewrite_adds_valid_queries(self):
        rewrite_client = FakeRewriteClient({"queries": ["8个RJ45交换机", "8口以太网接口"]})
        dictionary = TerminologyDictionary.from_mapping({"电口": {"canonical": "RJ-45", "aliases": ["RJ45"]}})
        service = QueryUnderstandingService(
            dictionary=dictionary,
            rewrite_client=rewrite_client,
            config=QueryUnderstandingConfig(enabled=True, rewrite_enabled=True, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertEqual(1, len(rewrite_client.calls))
        self.assertIn("8个RJ45交换机", result.retrieval_queries)
        self.assertIn("RJ-45", result.expanded_terms)
        self.assertEqual("mixed", result.source)

    def test_invalid_llm_rewrite_is_ignored(self):
        rewrite_client = FakeRewriteClient("not-json")
        dictionary = TerminologyDictionary.from_mapping({"电口": {"canonical": "RJ-45", "aliases": ["RJ45"]}})
        service = QueryUnderstandingService(
            dictionary=dictionary,
            rewrite_client=rewrite_client,
            config=QueryUnderstandingConfig(enabled=True, rewrite_enabled=True, max_queries=5),
        )

        result = service.understand("8个电口")

        self.assertNotIn("not-json", result.retrieval_queries)
        self.assertIn("8个RJ-45", result.retrieval_queries)


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
