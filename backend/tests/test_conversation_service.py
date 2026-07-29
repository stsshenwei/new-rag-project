import tempfile
import unittest
from pathlib import Path

from app.services.memory.conversation_repository import ConversationRepository
from app.services.memory.conversation_service import ConversationService


class FakeSummarizer:
    def __init__(self):
        self.calls = []

    def summarize(self, previous_summary, messages):
        self.calls.append({"previous_summary": previous_summary, "messages": messages})
        return "Summary: user prefers Chinese and is building RAG memory."


class ConversationServiceTests(unittest.TestCase):
    def make_service(self, recent_limit=3, summary_threshold=5):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        repository = ConversationRepository(Path(tmpdir.name) / "memory.sqlite3")
        summarizer = FakeSummarizer()
        service = ConversationService(
            repository=repository,
            recent_message_limit=recent_limit,
            summary_message_threshold=summary_threshold,
            summarizer=summarizer,
        )
        return service, repository, summarizer

    def test_get_or_create_conversation_creates_when_missing(self):
        service, repository, _ = self.make_service()

        conversation = service.get_or_create_conversation(None)

        self.assertTrue(conversation["id"].startswith("conv_"))
        self.assertIsNotNone(repository.get_conversation(conversation["id"]))

    def test_get_or_create_conversation_reuses_existing_id(self):
        service, repository, _ = self.make_service()
        existing = repository.create_conversation(title="Existing")

        conversation = service.get_or_create_conversation(existing["id"])

        self.assertEqual(existing["id"], conversation["id"])
        self.assertEqual("Existing", conversation["title"])

    def test_build_context_returns_summary_and_recent_window(self):
        service, repository, _ = self.make_service(recent_limit=2, summary_threshold=10)
        conversation = repository.create_conversation()
        repository.update_summary(conversation["id"], "Earlier: project uses FastAPI.")
        repository.append_message(conversation["id"], "user", "first", {})
        repository.append_message(conversation["id"], "assistant", "second", {})
        repository.append_message(conversation["id"], "user", "third", {})

        context = service.build_context(conversation["id"])

        self.assertEqual("Earlier: project uses FastAPI.", context["summary"])
        self.assertEqual(["assistant", "user"], [item["role"] for item in context["recent_messages"]])
        self.assertEqual(["second", "third"], [item["content"] for item in context["recent_messages"]])

    def test_maybe_summarize_updates_summary_when_threshold_exceeded(self):
        service, repository, summarizer = self.make_service(recent_limit=2, summary_threshold=3)
        conversation = repository.create_conversation()
        for index in range(4):
            repository.append_message(conversation["id"], "user", f"message {index}", {})

        summary = service.maybe_summarize(conversation["id"])

        loaded = repository.get_conversation(conversation["id"])
        self.assertEqual("Summary: user prefers Chinese and is building RAG memory.", summary)
        self.assertEqual(summary, loaded["summary"])
        self.assertEqual(["message 0", "message 1"], [item["content"] for item in summarizer.calls[0]["messages"]])

    def test_maybe_summarize_does_nothing_below_threshold(self):
        service, repository, summarizer = self.make_service(recent_limit=2, summary_threshold=10)
        conversation = repository.create_conversation()
        repository.append_message(conversation["id"], "user", "only", {})

        self.assertEqual("", service.maybe_summarize(conversation["id"]))
        self.assertEqual([], summarizer.calls)


if __name__ == "__main__":
    unittest.main()
