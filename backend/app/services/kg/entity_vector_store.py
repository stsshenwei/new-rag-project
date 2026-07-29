import json
from typing import Any

from app.models.kg_models import Entity
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.retrieval.embedding_provider import EmbeddingProvider


ENTITY_VECTOR_FIELDS = {
    "id",
    "entity_id",
    "entity_type",
    "entity_name",
    "tenant_id",
    "workspace_id",
    "knowledge_base_id",
    "description",
    "aliases",
    "dense_vector",
    "metadata",
}


def _create_or_load_entity_collection(uri: str, token: str, collection_name: str, embedding_dim: int):
    try:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
    except Exception as exc:
        raise RuntimeError("Milvus entity vector support requires pymilvus.") from exc

    connect_kwargs: dict[str, Any] = {"alias": f"{collection_name}_alias", "uri": uri}
    if token:
        connect_kwargs["token"] = token
    connections.connect(**connect_kwargs)
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        _validate_entity_collection_schema(collection, collection_name)
        collection.load()
        return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
        FieldSchema(name="entity_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="entity_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="entity_name", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="workspace_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="knowledge_base_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="aliases", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
        FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=8192),
    ]
    schema = CollectionSchema(fields=fields, description="KG entity vectors")
    collection = Collection(collection_name, schema=schema)
    collection.create_index(
        field_name="dense_vector",
        index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},
    )
    collection.load()
    return collection


def _validate_entity_collection_schema(collection: Any, collection_name: str) -> None:
    schema = getattr(collection, "schema", None)
    fields = getattr(schema, "fields", []) if schema is not None else []
    field_names = {str(getattr(field, "name", "")) for field in fields}
    missing = sorted(ENTITY_VECTOR_FIELDS - field_names)
    if missing:
        raise RuntimeError(f"Milvus collection {collection_name!r} is missing entity vector fields {missing}.")


class MilvusEntityVectorStore:
    def __init__(
        self,
        uri: str,
        token: str,
        collection_name: str,
        embedding_dim: int,
        embedding_provider: EmbeddingProvider,
        collection: Any | None = None,
    ):
        self.uri = uri
        self.token = token
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.embedding_provider = embedding_provider
        self._collection = collection or _create_or_load_entity_collection(uri, token, collection_name, embedding_dim)

    def upsert_entities(self, entities: list[Entity]) -> None:
        if not entities:
            return
        embeddings = self.embedding_provider.embed_batch([self._embedding_text(entity) for entity in entities])
        rows = []
        for idx, entity in enumerate(entities):
            workspace_id = str(entity.metadata.get("workspace_id", entity.metadata.get("tenant_id", "default-workspace")))
            tenant_id = str(entity.metadata.get("tenant_id", workspace_id))
            knowledge_base_id = str(entity.metadata.get("knowledge_base_id", "default-knowledge-base"))
            rows.append(
                {
                    "id": f"{knowledge_base_id}:{entity.id}",
                    "entity_id": entity.id,
                    "entity_type": entity.type,
                    "entity_name": entity.name,
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                    "knowledge_base_id": knowledge_base_id,
                    "description": entity.description,
                    "aliases": json.dumps(entity.aliases, ensure_ascii=False),
                    "dense_vector": embeddings[idx],
                    "metadata": json.dumps(entity.metadata, ensure_ascii=False),
                }
            )
        self._collection.insert(rows)
        flush = getattr(self._collection, "flush", None)
        if callable(flush):
            flush()

    def search_similar(
        self,
        entity: Entity,
        top_k: int = 3,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        if scope is None and entity.metadata.get("workspace_id") and entity.metadata.get("knowledge_base_id"):
            scope = KnowledgeBaseScope(
                workspace_id=str(entity.metadata["workspace_id"]),
                selected_knowledge_base_ids=(str(entity.metadata["knowledge_base_id"]),),
            )
        scope = scope or KnowledgeBaseScope("default-workspace", ("default-knowledge-base",), compatibility_default=True)
        query_embedding = self.embedding_provider.embed_text(self._embedding_text(entity))
        result = self._collection.search(
            data=[query_embedding],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k,
            expr=_scope_expr(scope),
            output_fields=["entity_id", "entity_type", "entity_name", "description", "aliases", "metadata"],
        )
        matches: list[dict[str, Any]] = []
        for hit in (result[0] if result else []):
            raw = getattr(hit, "entity", None)
            aliases = json.loads(_entity_get(raw, "aliases") or "[]")
            metadata = json.loads(_entity_get(raw, "metadata") or "{}")
            matches.append(
                {
                    "entity": Entity(
                        id=str(_entity_get(raw, "entity_id")),
                        type=str(_entity_get(raw, "entity_type")),
                        name=str(_entity_get(raw, "entity_name")),
                        description=str(_entity_get(raw, "description") or ""),
                        aliases=aliases,
                        metadata=metadata,
                    ),
                    "score": float(getattr(hit, "score", 0.0)),
                }
            )
        return matches

    def _embedding_text(self, entity: Entity) -> str:
        aliases = ", ".join(entity.aliases)
        return "\n".join(part for part in [entity.name, entity.type, aliases, entity.description] if part)


def _entity_get(entity: Any, field: str) -> Any:
    if entity is None:
        return ""
    if hasattr(entity, "get"):
        return entity.get(field)
    return getattr(entity, field, "")


def _scope_expr(scope: KnowledgeBaseScope) -> str:
    ids = ", ".join(f'"{item}"' for item in scope.selected_knowledge_base_ids)
    return f'workspace_id == "{scope.workspace_id}" and knowledge_base_id in [{ids}]'
