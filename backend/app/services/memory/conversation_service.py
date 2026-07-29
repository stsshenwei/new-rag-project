from typing import Any, Protocol

from app.services.memory.conversation_repository import ConversationRepository


class ConversationSummarizer(Protocol):
    def summarize(self, previous_summary: str, messages: list[dict[str, Any]]) -> str:
        ...


class SimpleConversationSummarizer:
    def summarize(self, previous_summary: str, messages: list[dict[str, Any]]) -> str:
        lines = []
        if previous_summary:
            lines.append(previous_summary)
        for message in messages:
            role = message.get("role", "unknown")
            content = str(message.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)[-4000:]


class ConversationService:
    def __init__(
        self,
        repository: ConversationRepository,
        recent_message_limit: int = 10,
        summary_message_threshold: int = 20,
        summarizer: ConversationSummarizer | None = None,
    ):
        self.repository = repository
        self.recent_message_limit = max(1, recent_message_limit)
        self.summary_message_threshold = max(self.recent_message_limit + 1, summary_message_threshold)
        self.summarizer = summarizer or SimpleConversationSummarizer()

    def get_or_create_conversation(self, conversation_id: str | None) -> dict[str, Any]:
        if conversation_id:
            existing = self.repository.get_conversation(conversation_id)
            if existing is not None:
                return existing
        return self.repository.create_conversation()

    def build_context(self, conversation_id: str) -> dict[str, Any]:
        conversation = self.repository.get_conversation(conversation_id) or {}
        return {
            "conversation_id": conversation_id,
            "summary": conversation.get("summary", ""),
            "recent_messages": self.repository.list_recent_messages(conversation_id, self.recent_message_limit),
        }

    def maybe_summarize(self, conversation_id: str) -> str:
        messages = self.repository.list_messages(conversation_id)
        if len(messages) < self.summary_message_threshold:
            return ""
        old_messages = messages[: -self.recent_message_limit]
        if not old_messages:
            return ""
        conversation = self.repository.get_conversation(conversation_id) or {}
        summary = self.summarizer.summarize(str(conversation.get("summary", "")), old_messages)
        self.repository.update_summary(conversation_id, summary)
        return summary
