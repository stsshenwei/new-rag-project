import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.models.knowledge_base import KnowledgeBaseScope
from app.services.rag_service import RAGService


class FakeVectorStore:
    def __init__(self):
        self.persist_dir = Path(tempfile.mkdtemp())

    def count(self):
        return 0


class QuickAnswerParityTests(unittest.TestCase):
    def make_service(self):
        context_template = Path(__file__).resolve().parents[1] / "config" / "prompt_templates" / "context_template.yaml"
        service = RAGService(
            vector_store=FakeVectorStore(),
            llm_client=SimpleNamespace(),
            chat_model="test",
            system_prompt="test",
            data_dir=tempfile.mkdtemp(),
            top_k=3,
            min_relevance_score=0.0,
            chunk_size=80,
            chunk_overlap=10,
            agent_trace_stream_enabled=True,
            context_template_path=str(context_template),
        )
        service._last_retrieval_debug = {
            "query_understanding": {
                "normalized_query": "TSFP-CU1M-DAC 适配交换机",
                "retrieval_queries": ["可适配万兆堆叠线缆的交换机", "TSFP-CU1M-DAC 交换机"],
                "applied_terms": [{"term": "万兆堆叠线缆", "canonical": "TSFP-CU1M-DAC"}],
            },
            "retrieval_stages": {
                "dense": {"query_count": 2, "candidate_count": 4},
                "keyword": {"query_count": 2, "candidate_count": 3},
                "fusion": {"input_count": 7, "output_count": 5},
            },
            "query_expansion": {"enabled": True, "used": False, "final_candidate_count": 5},
            "fused_results": [{"id": "f1"}, {"id": "f2"}],
            "reranked_results": [{"id": "r1"}],
        }
        return service

    def test_quick_trace_has_weknora_style_stage_order_and_metadata(self):
        service = self.make_service()
        hits = [
            {
                "content": "DH-NS7600 支持 TSFP-CU1M-DAC。",
                "metadata": {"source": "switch-a.md", "matched_child_ids": ["c1", "c2"], "chunk_id": "p1"},
            },
            {
                "content": "DH-NS5500 仅部分型号支持。",
                "metadata": {"source": "switch-b.md", "matched_child_ids": ["c3"]},
            },
        ]

        scope = KnowledgeBaseScope(workspace_id="ws-1", selected_knowledge_base_ids=("kb-a",), document_ids=())
        trace = service.build_chat_agent_trace(
            "可适配万兆堆叠线缆的交换机",
            hits,
            scope=scope,
            sources=[{"source": "switch-a.md"}, {"source": "switch-b.md"}],
        )

        self.assertEqual(
            ["UnderstandQuestion", "RetrieveKnowledgeBase", "ReadEvidence", "SynthesizeAnswer", "Complete"],
            [step["stage"] for step in trace],
        )
        self.assertEqual(["c1", "c2", "p1", "c3"], trace[-1]["source_chunk_ids"])
        metadata = trace[1]["metadata"]
        self.assertTrue(metadata["quick_rag"])
        self.assertEqual("quick", metadata["chat_mode"])
        self.assertEqual(2, metadata["retrieval_query_count"])
        self.assertEqual(5, metadata["candidate_count"])
        self.assertEqual(2, metadata["hit_count"])
        self.assertEqual(2, metadata["cited_document_count"])
        self.assertEqual(["kb-a"], metadata["knowledge_base_scope"]["knowledge_base_ids"])
        self.assertFalse(metadata["insufficient_evidence"])
        trace_text = str(trace)
        for private_key in ["chain_of_thought", "scratchpad", "private_reasoning", "raw_prompt", "memory_context"]:
            self.assertNotIn(private_key, trace_text)

    def test_quick_trace_marks_insufficient_evidence_without_sources(self):
        service = self.make_service()

        trace = service.build_chat_agent_trace("不存在的型号支持什么速率？", [])

        self.assertEqual("partial", trace[2]["status"])
        self.assertEqual("partial", trace[-1]["status"])
        self.assertTrue(trace[-1]["metadata"]["insufficient_evidence"])
        self.assertIn("无法确定", trace[2]["summary"])

    def test_agent_trace_stream_flag_still_disables_quick_trace(self):
        service = self.make_service()
        service.agent_trace_stream_enabled = False

        self.assertEqual([], service.build_chat_agent_trace("问题", [{"metadata": {"source": "a.md"}}]))

    def test_compatibility_answer_guidance_requires_grounded_markdown(self):
        service = self.make_service()
        guidance = service._build_answer_style_guidance(
            "TSFP-CU1M-DAC 可适配哪些交换机？",
            "DH-NS7600 完全适配。DH-NS5500 仅部分型号支持。传输速率：10Gbps。",
        )

        self.assertIn("结构化 Markdown", guidance)
        self.assertIn("完全适配系列", guidance)
        self.assertIn("部分型号适配系列", guidance)
        self.assertIn("技术参数", guidance)
        self.assertIn("同一产品或同一来源", guidance)
        self.assertIn("根据提供的文档无法确定", guidance)

    def test_support_port_authentication_and_parameter_questions_use_guidance(self):
        service = self.make_service()
        questions = [
            "DH-P5000-08GP-AC 支持哪些 ONU 认证方式？",
            "DH-P204 ONU 的业务端口配置及接入速率是多少？",
            "无线产品 DH-AC2048 支持哪些安全认证机制？",
            "这根线缆的工作温度和湿度要求是多少？",
            "Which switches are compatible with this adapter?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertIn("根据提供的文档无法确定", service._build_answer_style_guidance(question, ""))

    def test_product_filter_questions_get_selection_guidance(self):
        service = self.make_service()
        guidance = service._build_answer_style_guidance(
            "找出24个光口的交换机",
            "DH-NS5500-24GF4XF 支持24个光口和双电源。",
        )

        self.assertIn("选型建议", guidance)
        self.assertIn("需求场景", guidance)
        self.assertIn("推荐型号", guidance)
        self.assertIn("同一产品或同一来源", guidance)
        self.assertIn("24个光口", guidance)
        self.assertIn("24GT", guidance)

    def test_unrelated_fact_question_uses_default_markdown_without_special_tables(self):
        service = self.make_service()
        guidance = service._build_answer_style_guidance("Bee 是什么？", "Bee 是知识助手。")

        self.assertIn("Markdown", guidance)
        self.assertIn("直接结论", guidance)
        self.assertIn("根据提供的文档无法确定", guidance)
        self.assertNotIn("完全适配系列", guidance)
        self.assertNotIn("部分型号适配系列", guidance)


if __name__ == "__main__":
    unittest.main()
