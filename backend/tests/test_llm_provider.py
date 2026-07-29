import unittest
from types import SimpleNamespace

from app.services.retrieval.llm_provider import INSUFFICIENT_CONTEXT_ANSWER, OpenAICompatibleLLMProvider
from app.services.retrieval.retrieval_models import BuiltContext


class FakeCompletions:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.answer))])


class FakeClient:
    def __init__(self, answer):
        self.chat = SimpleNamespace(completions=FakeCompletions(answer))


class LLMProviderTests(unittest.TestCase):
    def test_generate_answer_returns_structured_answer_with_citations(self):
        client = FakeClient("Use --timeout 30.")
        provider = OpenAICompatibleLLMProvider(client, model="qwen-plus", include_debug_info=True)
        context = BuiltContext(
            question="q",
            text="[1] file=manual.pdf\nUse --timeout 30.",
            selected_parent_chunks=[
                {
                    "doc_id": "doc-1",
                    "file_name": "manual.pdf",
                    "parent_id": "p1",
                    "title_path": "CLI/Flags",
                    "page_start": 5,
                    "page_end": 5,
                    "content": "Use --timeout 30.",
                    "matched_children": [{"chunk_id": "c1", "summary": "--timeout 30"}],
                }
            ],
            token_count=20,
        )

        answer = provider.generate_answer("How set timeout?", context)

        self.assertIn("Answer only from the supplied context", client.chat.completions.calls[0]["messages"][0]["content"])
        self.assertEqual("Use --timeout 30.", answer.answer)
        self.assertEqual("doc-1", answer.citations[0].doc_id)
        self.assertEqual("manual.pdf", answer.citations[0].file_name)
        self.assertEqual("c1", answer.used_chunks[0])
        self.assertIsNotNone(answer.debug_info)

    def test_generate_answer_uses_insufficient_context_answer(self):
        client = FakeClient("")
        provider = OpenAICompatibleLLMProvider(client, model="qwen-plus", include_debug_info=False)
        context = BuiltContext(question="q", text="", selected_parent_chunks=[], token_count=0)

        answer = provider.generate_answer("unknown?", context)

        self.assertEqual(INSUFFICIENT_CONTEXT_ANSWER, answer.answer)
        self.assertEqual(0.0, answer.confidence)
        self.assertIsNone(answer.debug_info)


if __name__ == "__main__":
    unittest.main()
