import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from app.services.agent_prompt_templates import PromptTemplateCatalog, PromptTemplateError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryUnderstandingConfig:
    enabled: bool = True
    rewrite_enabled: bool = False
    intent_detection_enabled: bool = False
    max_queries: int = 5
    language: str = "zh-CN"


@dataclass(frozen=True)
class TerminologyEntry:
    term: str
    canonical: str
    aliases: tuple[str, ...] = ()


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
            '{"queries":["..."]}. Keep deterministic dictionary canonical terms.'
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


class TerminologyDictionary:
    def __init__(self, entries: dict[str, TerminologyEntry] | None = None):
        self.entries = entries or {}

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any] | None) -> "TerminologyDictionary":
        entries: dict[str, TerminologyEntry] = {}
        for term, raw_entry in (mapping or {}).items():
            if not isinstance(term, str) or not isinstance(raw_entry, dict):
                continue
            canonical = raw_entry.get("canonical")
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            aliases = raw_entry.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []
            entries[term] = TerminologyEntry(
                term=term,
                canonical=canonical.strip(),
                aliases=tuple(alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip()),
            )
        return cls(entries)


def load_terminology_dictionary(path: str | Path | None) -> TerminologyDictionary:
    if not path:
        return TerminologyDictionary()
    terms_path = Path(path)
    if not terms_path.exists():
        return TerminologyDictionary()
    try:
        loaded = yaml.safe_load(terms_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            return TerminologyDictionary()
        return TerminologyDictionary.from_mapping(loaded.get("terms"))
    except Exception as exc:
        logger.warning("Failed to load query terminology dictionary %s: %s", terms_path, exc)
        return TerminologyDictionary()


class QueryUnderstandingService:
    def __init__(
        self,
        dictionary: TerminologyDictionary | None = None,
        config: QueryUnderstandingConfig | None = None,
        rewrite_client: QueryRewriteClient | None = None,
        intent_client: QueryIntentClient | None = None,
    ):
        self.dictionary = dictionary or TerminologyDictionary()
        self.config = config or QueryUnderstandingConfig()
        self.rewrite_client = rewrite_client
        self.intent_client = intent_client

    def understand(self, query: str) -> QueryUnderstandingResult:
        raw_query = query.strip()
        if not raw_query:
            return QueryUnderstandingResult(original_query=query, normalized_query=query, retrieval_queries=[query])
        if not self.config.enabled:
            return self._fallback(raw_query)

        result = self._dictionary_understanding(raw_query)
        result.retrieval_queries.extend(self._domain_retrieval_queries(raw_query))
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

    def _domain_retrieval_queries(self, query: str) -> list[str]:
        queries: list[str] = []
        splitter_match = re.search(r"(\d+)\s*个?\s*分光器", query, flags=re.IGNORECASE)
        if splitter_match and "olt" in query.lower():
            count = int(splitter_match.group(1))
            rounded_capacity = ((count + 7) // 8) * 8
            queries.extend(
                [
                    f"OLT 至少{count}个PON口 GPON接口容量",
                    f"{rounded_capacity}口盒式OLT GPON口",
                    "OLT 业务槽位 GPON业务板卡 PON口数量",
                    "机框式OLT 最大GPON接口 扩展能力",
                ]
            )
        return queries

    def _fallback(self, query: str) -> QueryUnderstandingResult:
        return QueryUnderstandingResult(
            original_query=query,
            normalized_query=query,
            retrieval_queries=[query],
            source="fallback",
        )

    def _dictionary_understanding(self, query: str) -> QueryUnderstandingResult:
        normalized_query = query
        expanded_terms: list[str] = []
        retrieval_queries = [query]
        applied_terms: list[dict[str, str]] = []

        for term, entry in self.dictionary.entries.items():
            if term not in query and entry.canonical not in query and not any(alias in query for alias in entry.aliases):
                continue
            replacement_terms = [entry.canonical, *entry.aliases]
            normalized_query = self._replace_known_term(normalized_query, term, entry.canonical, entry.aliases)
            expanded_terms.extend([term, entry.canonical, *entry.aliases])
            applied_terms.append({"term": term, "canonical": entry.canonical})
            for replacement in replacement_terms:
                retrieval_queries.append(self._replace_known_term(query, term, replacement, entry.aliases))

        source = "dictionary" if applied_terms else "fallback"
        if source == "fallback":
            normalized_query = query
        elif normalized_query not in retrieval_queries:
            retrieval_queries.insert(1, normalized_query)

        return QueryUnderstandingResult(
            original_query=query,
            normalized_query=normalized_query,
            expanded_terms=self._dedupe(expanded_terms),
            retrieval_queries=self._dedupe_and_cap(retrieval_queries),
            applied_terms=applied_terms,
            source=source,
        )

    def _replace_known_term(self, query: str, term: str, replacement: str, aliases: tuple[str, ...]) -> str:
        updated = query
        candidates = [term, *aliases]
        for candidate in candidates:
            if candidate and candidate in updated:
                updated = updated.replace(candidate, replacement)
        return updated

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
            logger.warning("Query rewrite failed, using dictionary/raw queries: %s", exc)
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
            logger.warning("Query intent detection failed, using dictionary/raw intent: %s", exc)
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
