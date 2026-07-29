import tempfile
import unittest
from pathlib import Path

from app.services.memory.memory_repository import MemoryRepository
from app.services.memory.memory_service import MemoryService


class MemoryServiceTests(unittest.TestCase):
    def make_service(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        repository = MemoryRepository(Path(tmpdir.name) / "memory.sqlite3")
        return MemoryService(repository=repository), repository

    def test_process_exchange_saves_stable_preference(self):
        service, repository = self.make_service()

        updates = service.process_exchange(
            user_message="以后请用中文简洁回答。",
            assistant_message="好的。",
            conversation_id="conv-1",
            user_message_id="msg-1",
            memory_enabled=True,
        )

        memories = repository.list_active_memories()
        self.assertEqual(1, len(memories))
        self.assertEqual("preference", memories[0]["type"])
        self.assertIn("中文简洁回答", memories[0]["content"])
        self.assertEqual(updates[0]["id"], memories[0]["id"])

    def test_process_exchange_ignores_one_off_task(self):
        service, repository = self.make_service()

        updates = service.process_exchange(
            user_message="帮我运行一下测试。",
            assistant_message="测试通过。",
            conversation_id="conv-1",
            user_message_id="msg-1",
            memory_enabled=True,
        )

        self.assertEqual([], updates)
        self.assertEqual([], repository.list_active_memories())

    def test_process_exchange_rejects_sensitive_content(self):
        service, repository = self.make_service()

        updates = service.process_exchange(
            user_message="记住我的 OPENAI_API_KEY 是 sk-secret。",
            assistant_message="好的。",
            conversation_id="conv-1",
            user_message_id="msg-1",
            memory_enabled=True,
        )

        self.assertEqual([], updates)
        self.assertEqual([], repository.list_active_memories())

    def test_process_exchange_merges_duplicate_preference(self):
        service, repository = self.make_service()

        service.process_exchange("以后请用中文回答。", "好的。", "conv-1", "msg-1")
        service.process_exchange("以后请用中文简洁回答。", "好的。", "conv-2", "msg-2")

        memories = repository.list_active_memories()
        self.assertEqual(1, len(memories))
        self.assertIn("中文简洁回答", memories[0]["content"])
        self.assertEqual("conv-2", memories[0]["source_conversation_id"])

    def test_process_exchange_respects_disabled_memory(self):
        service, repository = self.make_service()

        updates = service.process_exchange(
            user_message="以后请用中文回答。",
            assistant_message="好的。",
            conversation_id="conv-1",
            user_message_id="msg-1",
            memory_enabled=False,
        )

        self.assertEqual([], updates)
        self.assertEqual([], repository.list_active_memories())

    def test_explicit_remember_and_forget(self):
        service, repository = self.make_service()

        service.process_exchange("请记住我正在做RAG项目。", "好的。", "conv-1", "msg-1")
        self.assertEqual(1, len(repository.list_active_memories()))

        updates = service.process_exchange("忘记我正在做RAG项目。", "好的。", "conv-2", "msg-2")

        self.assertEqual("deleted", updates[0]["action"])
        self.assertEqual([], repository.list_active_memories())

    def test_recall_and_format_prompt_context(self):
        service, repository = self.make_service()
        repository.upsert_memory("user", "preference", "language", "用户偏好中文回答。", 0.9)
        repository.upsert_memory("project", "project_fact", "stack", "项目使用 FastAPI 和 Next.js。", 0.9)

        memories = service.recall_memories("怎么设计上下文？", limit=5)
        prompt_context = service.format_prompt_context(memories)

        self.assertEqual(2, len(memories))
        self.assertIn("[长期记忆]", prompt_context)
        self.assertIn("用户偏好中文回答。", prompt_context)
        self.assertIn("项目使用 FastAPI 和 Next.js。", prompt_context)


if __name__ == "__main__":
    unittest.main()
