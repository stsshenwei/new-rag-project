import logging
import time
from typing import Any

from app.services.retrieval.retrieval_models import Answer, BuiltContext, Citation

INSUFFICIENT_CONTEXT_ANSWER = "根据已检索到的资料，无法确定"


logger = logging.getLogger(__name__)


class OpenAICompatibleLLMProvider:
    def __init__(self, client: Any, model: str, include_debug_info: bool = False):
        self.client = client
        self.model = model
        self.include_debug_info = include_debug_info

    def generate_answer(self, question: str, context: BuiltContext) -> Answer:
        prompt = self._build_prompt(question, context)
        started = time.monotonic()
        logger.info(
            "provider.llm.start",
            extra={"provider": "openai-compatible", "model": self.model, "context_token_count": context.token_count},
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the supplied context. "
                            f"If the context is insufficient, answer exactly: {INSUFFICIENT_CONTEXT_ANSWER}. "
                            "Do not fabricate sources. Prefer citing file name, page, and section."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            logger.exception(
                "provider.llm.failed",
                extra={"provider": "openai-compatible", "model": self.model, "error_type": exc.__class__.__name__},
            )
            raise
        text = (completion.choices[0].message.content or "").strip()
        citations = self._citations_from_context(context)
        used_chunks = [child["chunk_id"] for parent in context.selected_parent_chunks for child in parent.get("matched_children", [])]
        debug_info = {"prompt": prompt, "context_token_count": context.token_count} if self.include_debug_info else None
        confidence = 0.0 if text == INSUFFICIENT_CONTEXT_ANSWER or not context.text.strip() else 0.7
        logger.info(
            "provider.llm.end",
            extra={
                "provider": "openai-compatible",
                "model": self.model,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "citations": len(citations),
            },
        )
        return Answer(answer=text or INSUFFICIENT_CONTEXT_ANSWER, citations=citations, used_chunks=used_chunks, confidence=confidence, debug_info=debug_info)

    def _build_prompt(self, question: str, context: BuiltContext) -> str:
        return (
            "Context:\n"
            f"{context.text if context.text.strip() else '(empty)'}\n\n"
            f"Question: {question}\n\n"
            "Rules: answer only from Context; if not enough evidence, use the required insufficient-context answer."
        )

    def _citations_from_context(self, context: BuiltContext) -> list[Citation]:
        citations: list[Citation] = []
        for parent in context.selected_parent_chunks:
            matched = parent.get("matched_children", []) or [{}]
            for child in matched:
                citations.append(
                    Citation(
                        doc_id=str(parent.get("doc_id", "")),
                        file_name=str(parent.get("file_name", "")),
                        chunk_id=str(child.get("chunk_id", "")),
                        parent_id=str(parent.get("parent_id", "")),
                        title_path=str(parent.get("title_path", "")),
                        page_start=parent.get("page_start"),
                        page_end=parent.get("page_end"),
                        summary=child.get("summary") or str(parent.get("content", ""))[:240],
                    )
                )
        return citations
