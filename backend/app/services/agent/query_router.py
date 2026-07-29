from __future__ import annotations

import re

from app.models.agentic_retrieval import QueryRoute


class QueryRouter:
    def route(self, question: str) -> QueryRoute:
        text = (question or "").strip()
        lower = text.lower()
        if not text:
            return QueryRoute(
                question_type="fact",
                confidence=0.0,
                metadata={"fallback": True, "uncertainty": "empty_question"},
            )

        question_type = "fact"
        graph_intent = ""
        confidence = 0.75
        if self._contains(lower, ["which source", "source", "citation", "出处", "来源", "哪份文档"]):
            question_type = "source"
        elif self._contains(lower, ["how do i", "how to", "configure", "setup", "install", "如何", "怎么"]):
            question_type = "howto"
        elif self._contains(lower, ["error", "failed", "failure", "exception", "timeout", "troubleshoot", "报错", "故障", "异常"]):
            question_type = "troubleshooting"
            graph_intent = "Error/Config/Service"
        elif self._contains(lower, ["compare", "versus", "vs", "difference", "对比", "比较"]):
            question_type = "comparison"
        elif self._contains(lower, ["impact", "affected", "affect", "unavailable", "down", "影响", "波及"]):
            question_type = "impact"
            graph_intent = "impact"
        elif self._contains(lower, ["depend", "dependency", "depends on", "依赖"]):
            question_type = "dependency"
            graph_intent = "path"
        elif self._contains(lower, ["summarize", "summary", "概括", "总结"]):
            question_type = "summary"
        elif self._contains(lower, ["should", "choose", "decide", "recommend", "是否应该", "选择", "决策", "帮我选", "选一款", "选型", "推荐"]):
            question_type = "decision"
        else:
            confidence = 0.65

        return QueryRoute(
            question_type=question_type,
            confidence=confidence,
            detected_entities=self._detect_entities(text),
            requested_sources=self._detect_requested_sources(text),
            graph_intent=graph_intent,
            metadata={"fallback": question_type == "fact" and confidence < 0.7, "uncertainty": "low" if confidence < 0.7 else "none"},
        )

    def _contains(self, text: str, needles: list[str]) -> bool:
        return any(needle in text for needle in needles)

    def _detect_entities(self, text: str) -> list[str]:
        entities = re.findall(r"\b[A-Z][A-Za-z0-9_-]*(?:\s+[A-Z][A-Za-z0-9_-]*)*\b", text)
        tech_terms = re.findall(r"\b[A-Za-z]+(?:DB|API|SQL|Redis|Gateway|Service|PostgreSQL)\b", text)
        return list(dict.fromkeys([*entities, *tech_terms]))[:6]

    def _detect_requested_sources(self, text: str) -> list[str]:
        matches = re.findall(r"[\w./-]+\.(?:md|txt|pdf|docx|html|json|csv)", text, flags=re.IGNORECASE)
        return list(dict.fromkeys(matches))
