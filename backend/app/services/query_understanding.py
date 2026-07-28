import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.agent_prompt_templates import PromptTemplateCatalog, PromptTemplateError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryUnderstandingConfig:
    enabled: bool = True
    rewrite_enabled: bool = False
    intent_detection_enabled: bool = False
    max_queries: int = 5
    language: str = "zh-CN"


@dataclass
class QueryUnderstandingResult:
    original_query: str
    normalized_query: str
    intent: str = "technical_document_search"
    constraints: list[dict[str, Any]] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    retrieval_queries: list[str] = field(default_factory=list)
    applied_terms: list[dict[str, str]] = field(default_factory=list)
    source: str = "fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "intent": self.intent,
            "constraints": self.constraints,
            "expanded_terms": self.expanded_terms,
            "retrieval_queries": self.retrieval_queries,
            "applied_terms": self.applied_terms,
            "source": self.source,
        }


class QueryRewriteClient(Protocol):
    def rewrite(self, query: str, understanding: QueryUnderstandingResult) -> Any:
        ...


class QueryIntentClient(Protocol):
    def detect(
        self,
        query: str,
        understanding: QueryUnderstandingResult,
        *,
        conversation_context: str = "",
        language: str = "zh-CN",
    ) -> Any:
        ...


class OpenAIQueryRewriteClient:
    def __init__(
        self,
        llm_client: Any,
        model: str,
        *,
        prompt_catalog: PromptTemplateCatalog | None = None,
        template_id: str = "query_rewrite",
    ):
        self.llm_client = llm_client
        self.model = model
        self.prompt_catalog = prompt_catalog
        self.template_id = template_id

    def rewrite(self, query: str, understanding: QueryUnderstandingResult) -> Any:
        system_content = (
            "Rewrite the user query for retrieval. Return strict JSON only: "
            '{"queries":["..."]}. Use language and domain knowledge to add bounded aliases, abbreviations, '
            "translations, and field-name variants without adding factual claims."
        )
        user_content = json.dumps(
            {
                "query": query,
                "normalized_query": understanding.normalized_query,
                "expanded_terms": understanding.expanded_terms,
            },
            ensure_ascii=False,
        )
        if self.prompt_catalog is not None:
            try:
                system_content = self.prompt_catalog.render(
                    self.template_id,
                    {
                        "query": query,
                        "normalized_query": understanding.normalized_query,
                        "expanded_terms": json.dumps(understanding.expanded_terms, ensure_ascii=False),
                    },
                    mode="quick",
                )
                user_content = query
            except PromptTemplateError as exc:
                logger.warning("Query rewrite prompt render failed, using built-in prompt: %s", exc)
        completion = self.llm_client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
        )
        return completion.choices[0].message.content or ""


class OpenAIQueryIntentClient:
    def __init__(
        self,
        llm_client: Any,
        model: str,
        *,
        prompt_catalog: PromptTemplateCatalog | None = None,
        template_id: str = "intent_detection",
    ):
        self.llm_client = llm_client
        self.model = model
        self.prompt_catalog = prompt_catalog
        self.template_id = template_id

    def detect(
        self,
        query: str,
        understanding: QueryUnderstandingResult,
        *,
        conversation_context: str = "",
        language: str = "zh-CN",
    ) -> Any:
        system_content = (
            "Classify the user request for document retrieval. Return strict JSON only: "
            '{"intent":"fact","constraints":[],"needs_graph":false,"needs_exact_match":false}.'
        )
        user_content = json.dumps(
            {
                "query": query,
                "normalized_query": understanding.normalized_query,
                "conversation_context": conversation_context,
                "language": language,
            },
            ensure_ascii=False,
        )
        if self.prompt_catalog is not None:
            try:
                system_content = self.prompt_catalog.render(
                    self.template_id,
                    {
                        "query": query,
                        "conversation_context": conversation_context,
                        "language": language,
                    },
                    mode="quick",
                )
                user_content = query
            except PromptTemplateError as exc:
                logger.warning("Query intent prompt render failed, using built-in prompt: %s", exc)
        completion = self.llm_client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
        )
        return completion.choices[0].message.content or ""


class QueryUnderstandingService:
    def __init__(
        self,
        config: QueryUnderstandingConfig | None = None,
        rewrite_client: QueryRewriteClient | None = None,
        intent_client: QueryIntentClient | None = None,
    ):
        self.config = config or QueryUnderstandingConfig()
        self.rewrite_client = rewrite_client
        self.intent_client = intent_client

    def understand(self, query: str) -> QueryUnderstandingResult:
        raw_query = query.strip()
        if not raw_query:
            return QueryUnderstandingResult(original_query=query, normalized_query=query, retrieval_queries=[query])
        if not self.config.enabled:
            return self._fallback(raw_query)

        result = self._fallback(raw_query)
        if self.config.intent_detection_enabled and self.intent_client is not None:
            if self._detect_intent(raw_query, result):
                result.source = "mixed" if result.source != "fallback" else "llm"
        if self.config.rewrite_enabled and self.rewrite_client is not None:
            rewrite_queries = self._rewrite_queries(raw_query, result)
            if rewrite_queries:
                result.retrieval_queries = self._dedupe_and_cap([*result.retrieval_queries, *rewrite_queries])
                result.source = "mixed" if result.source != "fallback" else "llm"
        result.retrieval_queries = self._dedupe_and_cap(result.retrieval_queries or [raw_query])
        return result

    def _fallback(self, query: str) -> QueryUnderstandingResult:
        return QueryUnderstandingResult(
            original_query=query,
            normalized_query=query,
            retrieval_queries=[query],
            source="fallback",
        )

    def _rewrite_queries(self, query: str, result: QueryUnderstandingResult) -> list[str]:
        try:
            raw_output = self.rewrite_client.rewrite(query, result) if self.rewrite_client else None
            if isinstance(raw_output, str):
                raw_output = json.loads(raw_output)
            if isinstance(raw_output, dict):
                raw_queries = raw_output.get("queries", [])
            elif isinstance(raw_output, list):
                raw_queries = raw_output
            else:
                return []
            return [item.strip() for item in raw_queries if isinstance(item, str) and item.strip()]
        except Exception as exc:
            logger.warning("Query rewrite failed, using the available raw/normalized queries: %s", exc)
            return []

    def _detect_intent(self, query: str, result: QueryUnderstandingResult) -> bool:
        try:
            raw_output = self.intent_client.detect(
                query,
                result,
                conversation_context="",
                language=self.config.language,
            ) if self.intent_client else None
            if isinstance(raw_output, str):
                raw_output = json.loads(raw_output)
            if not isinstance(raw_output, dict):
                return False
            intent = str(raw_output.get("intent") or "").strip()
            if intent:
                result.intent = intent
            constraints = raw_output.get("constraints", [])
            if isinstance(constraints, list):
                result.constraints = [item for item in constraints if isinstance(item, dict)]
            return bool(intent or result.constraints)
        except Exception as exc:
            logger.warning("Query intent detection failed, using the raw-query fallback: %s", exc)
            return False

    def _dedupe_and_cap(self, values: list[str]) -> list[str]:
        max_queries = max(1, int(self.config.max_queries or 1))
        return self._dedupe(values)[:max_queries]

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            result.append(cleaned)
            seen.add(cleaned)
        return result
