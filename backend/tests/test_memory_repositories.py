import tempfile
import unittest
from pathlib import Path

from app.services.memory.conversation_repository import ConversationRepository
from app.services.memory.memory_repository import MemoryRepository


class ConversationRepositoryTests(unittest.TestCase):
    def make_repo(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        return ConversationRepository(Path(tmpdir.name) / "memory.sqlite3")

    def test_create_append_list_and_update_summary(self):
        repo = self.make_repo()

        conversation = repo.create_conversation(title="RAG memory")
        user_message = repo.append_message(conversation["id"], "user", "Remember I prefer Chinese.", {"sources": []})
        assistant_message = repo.append_message(conversation["id"], "assistant", "I will remember that.", {})
        repo.update_summary(conversation["id"], "User prefers Chinese answers.")

        loaded = repo.get_conversation(conversation["id"])
        messages = repo.list_messages(conversation["id"])

        self.assertEqual("RAG memory", loaded["title"])
        self.assertEqual("User prefers Chinese answers.", loaded["summary"])
        self.assertEqual([user_message["id"], assistant_message["id"]], [item["id"] for item in messages])
        self.assertEqual(["user", "assistant"], [item["role"] for item in messages])
        self.assertEqual({"sources": []}, messages[0]["metadata_json"])

    def test_list_recent_messages_returns_latest_in_chronological_order(self):
        repo = self.make_repo()
        conversation = repo.create_conversation()
        for index in range(5):
            repo.append_message(conversation["id"], "user", f"message {index}", {})

        messages = repo.list_recent_messages(conversation["id"], limit=3)

        self.assertEqual(["message 2", "message 3", "message 4"], [item["content"] for item in messages])


class MemoryRepositoryTests(unittest.TestCase):
    def make_repo(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        return MemoryRepository(Path(tmpdir.name) / "memory.sqlite3")

    def test_upsert_merges_by_scope_and_normalized_key(self):
        repo = self.make_repo()

        first = repo.upsert_memory(
            scope="user",
            memory_type="preference",
            normalized_key="language",
            content="User prefers Chinese answers.",
            confidence=0.9,
            source_conversation_id="conv-1",
            source_message_id="msg-1",
        )
        second = repo.upsert_memory(
            scope="user",
            memory_type="preference",
            normalized_key="language",
            content="User prefers concise Chinese answers.",
            confidence=0.95,
            source_conversation_id="conv-2",
            source_message_id="msg-2",
        )

        memories = repo.list_active_memories()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, len(memories))
        self.assertEqual("User prefers concise Chinese answers.", memories[0]["content"])
        self.assertEqual(0.95, memories[0]["confidence"])
        self.assertEqual("conv-2", memories[0]["source_conversation_id"])

    def test_delete_memory_excludes_it_from_active_list(self):
        repo = self.make_repo()
        memory = repo.upsert_memory(
            scope="project",
            memory_type="project_fact",
            normalized_key="stack",
            content="Project uses FastAPI and Next.js.",
            confidence=0.9,
        )

        self.assertTrue(repo.delete_memory(memory["id"]))

        self.assertEqual([], repo.list_active_memories())
        deleted = repo.get_memory(memory["id"])
        self.assertEqual("deleted", deleted["status"])

    def test_delete_unknown_memory_returns_false(self):
        repo = self.make_repo()

        self.assertFalse(repo.delete_memory("missing"))


if __name__ == "__main__":
    unittest.main()
