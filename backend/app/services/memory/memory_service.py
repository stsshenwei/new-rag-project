import hashlib
import re
from typing import Any

from app.services.memory.memory_repository import MemoryRepository


class MemoryService:
    def __init__(self, repository: MemoryRepository, default_scope: str = "user", min_confidence: float = 0.75):
        self.repository = repository
        self.default_scope = default_scope
        self.min_confidence = min_confidence

    def recall_memories(self, question: str, limit: int = 8, scope: str | None = None) -> list[dict[str, Any]]:
        memories = self.repository.list_active_memories(scope=scope)
        query = question.lower()

        def score(memory: dict[str, Any]) -> tuple[int, float, str]:
            content = str(memory.get("content", "")).lower()
            overlap = sum(1 for token in self._tokens(query) if token and token in content)
            return (overlap, float(memory.get("confidence", 0.0)), str(memory.get("updated_at", "")))

        memories.sort(key=score, reverse=True)
        return memories[:limit]

    def format_prompt_context(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return ""
        lines = ["[长期记忆]"]
        for memory in memories:
            memory_type = memory.get("type", "memory")
            scope = memory.get("scope", "user")
            content = str(memory.get("content", "")).strip()
            if content:
                lines.append(f"- ({scope}/{memory_type}) {content}")
        return "\n".join(lines)

    def process_exchange(
        self,
        user_message: str,
        assistant_message: str,
        conversation_id: str,
        user_message_id: str,
        memory_enabled: bool = True,
    ) -> list[dict[str, Any]]:
        if not memory_enabled:
            return []
        text = user_message.strip()
        if not text or self._contains_sensitive_content(text):
            return []
        forget_updates = self._handle_forget(text)
        if forget_updates:
            return forget_updates

        candidate = self._extract_candidate(text)
        if candidate is None or candidate["confidence"] < self.min_confidence:
            return []
        memory = self.repository.upsert_memory(
            scope=candidate["scope"],
            memory_type=candidate["type"],
            normalized_key=candidate["normalized_key"],
            content=candidate["content"],
            confidence=candidate["confidence"],
            source_conversation_id=conversation_id,
            source_message_id=user_message_id,
        )
        return [{"action": "upserted", **memory}]

    def delete_memory(self, memory_id: str) -> bool:
        return self.repository.delete_memory(memory_id)

    def list_active_memories(self) -> list[dict[str, Any]]:
        return self.repository.list_active_memories()

    def _extract_candidate(self, text: str) -> dict[str, Any] | None:
        if any(marker in text for marker in ("记住", "请记住", "remember")):
            content = self._clean_memory_content(text)
            return {
                "scope": "project" if "项目" in content or "RAG" in content else self.default_scope,
                "type": "project_fact" if "项目" in content or "RAG" in content else "instruction",
                "normalized_key": self._normalized_key(content),
                "content": self._as_memory_sentence(content),
                "confidence": 0.95,
            }
        if self._looks_like_preference(text):
            content = self._as_memory_sentence(text)
            return {
                "scope": self.default_scope,
                "type": "preference",
                "normalized_key": self._preference_key(text),
                "content": content,
                "confidence": 0.9,
            }
        return None

    def _handle_forget(self, text: str) -> list[dict[str, Any]]:
        if not any(marker in text for marker in ("忘记", "不要记住", "forget")):
            return []
        target = re.sub(r"(请)?忘记|不要记住|forget", "", text, flags=re.IGNORECASE).strip(" 。.，,")
        updates = []
        for memory in self.repository.list_active_memories():
            content = str(memory.get("content", ""))
            if not target or target in content or any(token in content for token in self._tokens(target)):
                if self.repository.delete_memory(str(memory["id"])):
                    updates.append({"action": "deleted", **memory})
        return updates

    def _contains_sensitive_content(self, text: str) -> bool:
        lowered = text.lower()
        secret_markers = ["api_key", "apikey", "password", "token", "secret", "sk-"]
        return any(marker in lowered for marker in secret_markers)

    def _looks_like_preference(self, text: str) -> bool:
        return any(marker in text for marker in ("以后", "偏好", "喜欢", "请用", "回答")) and any(
            word in text for word in ("中文", "简洁", "英文", "详细")
        )

    def _preference_key(self, text: str) -> str:
        if "中文" in text or "英文" in text or "回答" in text:
            return "language"
        return self._normalized_key(text)

    def _normalized_key(self, text: str) -> str:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        return f"memory:{digest}"

    def _clean_memory_content(self, text: str) -> str:
        cleaned = re.sub(r"^(请)?记住", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"^remember", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" 。.，,")

    def _as_memory_sentence(self, text: str) -> str:
        cleaned = self._clean_memory_content(text)
        cleaned = re.sub(r"^以后请?", "用户偏好", cleaned)
        cleaned = cleaned.strip(" 。.，,")
        if cleaned.startswith("用户"):
            return f"{cleaned}。"
        return f"用户{cleaned}。"

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", text.lower())
