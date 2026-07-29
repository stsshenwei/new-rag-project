import json
from typing import Any, Protocol

from app.models.kg_models import Entity, KGExtractionResult, Relation, generated_id
from app.services.agent.agent_prompt_templates import PromptTemplateCatalog, PromptTemplateError


class KGExtractorProvider(Protocol):
    extractor_version: str

    def extract(
        self,
        doc_id: str,
        parent_id: str,
        chunk_id: str,
        title_path: str,
        content: str,
        page_start: int | None,
        page_end: int | None,
    ) -> KGExtractionResult:
        ...


def parse_kg_extraction_payload(
    payload: dict[str, Any],
    doc_id: str,
    parent_id: str,
    chunk_id: str,
    page_start: int | None,
    page_end: int | None,
    extractor_version: str,
) -> KGExtractionResult:
    entities = []
    for item in payload.get("entities", []) or []:
        name = str(item.get("name", "")).strip()
        entity_type = str(item.get("type", "")).strip()
        if not name or not entity_type:
            raise ValueError("Extracted entity requires name and type")
        entities.append(
            Entity(
                id=str(item.get("id") or generated_id(entity_type, name)),
                type=entity_type,
                name=name,
                description=str(item.get("description", "")),
                aliases=[str(alias) for alias in item.get("aliases", []) if str(alias).strip()],
                confidence=float(item.get("confidence", 1.0) or 0.0),
                metadata={"evidence": item.get("evidence", "")},
            )
        )

    relations = []
    for item in payload.get("relations", []) or []:
        source = str(item.get("source", item.get("source_entity_id", ""))).strip()
        target = str(item.get("target", item.get("target_entity_id", ""))).strip()
        relation_type = str(item.get("relation", item.get("relation_type", ""))).strip()
        if not source or not target or not relation_type:
            raise ValueError("Extracted relation requires source, target, and relation")
        relations.append(
            Relation(
                source_entity_id=source,
                target_entity_id=target,
                relation_type=relation_type,
                description=str(item.get("description", "")),
                confidence=float(item.get("confidence", 1.0) or 0.0),
                source_chunk_id=chunk_id,
                doc_id=doc_id,
                page_start=page_start,
                page_end=page_end,
                extractor_version=extractor_version,
                metadata={"evidence": item.get("evidence", ""), "parent_id": parent_id},
            )
        )
    return KGExtractionResult(entities=entities, relations=relations)


class OpenAIKGExtractor:
    def __init__(
        self,
        client: Any,
        model: str,
        extractor_version: str = "kg-v1",
        *,
        prompt_catalog: PromptTemplateCatalog | None = None,
        template_id: str = "graph_extraction",
    ):
        self.client = client
        self.model = model
        self.extractor_version = extractor_version
        self.prompt_catalog = prompt_catalog
        self.template_id = template_id

    def extract(
        self,
        doc_id: str,
        parent_id: str,
        chunk_id: str,
        title_path: str,
        content: str,
        page_start: int | None,
        page_end: int | None,
    ) -> KGExtractionResult:
        prompt = (
            "Extract knowledge graph entities and relations as JSON with keys entities and relations.\n"
            "Entity fields: name, type, description, aliases, confidence, evidence.\n"
            "Relation fields: source, target, relation, description, confidence, evidence.\n"
            f"doc_id={doc_id}\nparent_id={parent_id}\ntitle_path={title_path}\ncontent:\n{content}"
        )
        if self.prompt_catalog is not None:
            try:
                prompt = self.prompt_catalog.render(
                    self.template_id,
                    {"document_name": title_path or doc_id, "content": content},
                    mode="postprocess",
                )
            except PromptTemplateError:
                pass
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "Return only valid JSON for knowledge graph extraction."},
                {"role": "user", "content": prompt},
            ],
        )
        text = completion.choices[0].message.content or "{}"
        payload = json.loads(text)
        return parse_kg_extraction_payload(
            payload,
            doc_id=doc_id,
            parent_id=parent_id,
            chunk_id=chunk_id,
            page_start=page_start,
            page_end=page_end,
            extractor_version=self.extractor_version,
        )
