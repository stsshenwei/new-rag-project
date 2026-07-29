from pathlib import Path
from typing import Any

from app.models.document_models import Chunk
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.retrieval.embedding_provider import EmbeddingProvider


class MilvusSchemaResetRequired(RuntimeError):
    pass


def _create_or_load_collection(uri: str, token: str, collection_name: str, embedding_dim: int, bm25_enabled: bool = False):
    try:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, Function, FunctionType, connections, utility
    except Exception as exc:
        raise RuntimeError("Milvus support requires pymilvus. Please install backend requirements.") from exc

    connect_kwargs: dict[str, Any] = {"alias": "default", "uri": uri}
    if token:
        connect_kwargs["token"] = token
    connections.connect(**connect_kwargs)
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        _validate_existing_collection_schema(collection, collection_name, bm25_enabled=bm25_enabled)
        collection.load()
        return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="workspace_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="knowledge_base_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="strategy", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="processing_version", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="size_unit", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="image_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="storage_key", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="source_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="title_path", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="page_start", dtype=DataType.INT64),
        FieldSchema(name="page_end", dtype=DataType.INT64),
    ]
    functions = []
    if bm25_enabled:
        fields.extend(
            [
                FieldSchema(name="bm25_text", dtype=DataType.VARCHAR, max_length=8192, enable_analyzer=True),
                FieldSchema(name="bm25_sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
            ]
        )
        functions.append(
            Function(
                name="bm25_function",
                function_type=FunctionType.BM25,
                input_field_names=["bm25_text"],
                output_field_names=["bm25_sparse"],
            )
        )
    schema = CollectionSchema(fields=fields, description="RAG child/table chunk vectors", functions=functions or None)
    collection = Collection(collection_name, schema=schema)
    collection.create_index(
        field_name="embedding",
        index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},
    )
    collection.create_index(field_name="workspace_id", index_params={"index_type": "INVERTED"})
    collection.create_index(field_name="knowledge_base_id", index_params={"index_type": "INVERTED"})
    if bm25_enabled:
        collection.create_index(
            field_name="bm25_sparse",
            index_params={"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25", "params": {}},
        )
    collection.load()
    return collection


def _validate_existing_collection_schema(collection: Any, collection_name: str, bm25_enabled: bool) -> None:
    schema = getattr(collection, "schema", None)
    fields = getattr(schema, "fields", []) if schema is not None else []
    field_names = {str(getattr(field, "name", "")) for field in fields}
    required = {
        "id",
        "embedding",
        "chunk_id",
        "doc_id",
        "workspace_id",
        "knowledge_base_id",
        "parent_id",
        "chunk_type",
        "strategy",
        "processing_version",
        "size_unit",
        "image_id",
        "storage_key",
        "source_type",
        "title_path",
        "page_start",
        "page_end",
    }
    if bm25_enabled:
        required.update({"bm25_text", "bm25_sparse"})
    missing = sorted(required - field_names)
    if missing:
        raise MilvusSchemaResetRequired(
            f"Milvus collection {collection_name!r} is missing final-schema fields {missing}. "
            "Run the clean-rebuild CLI before starting normal ingest or retrieval."
        )


class MilvusVectorStore:
    def __init__(
        self,
        uri: str,
        token: str,
        collection_name: str,
        embedding_dim: int,
        embedding_provider: EmbeddingProvider,
        state_dir: str | Path = "./vector_db",
        bm25_enabled: bool = False,
    ):
        self.uri = uri
        self.token = token
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.embedding_provider = embedding_provider
        self.bm25_enabled = bm25_enabled
        self.persist_dir = Path(state_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.reset_required = False
        try:
            self._collection = _create_or_load_collection(
                uri, token, collection_name, embedding_dim, bm25_enabled=bm25_enabled
            )
        except MilvusSchemaResetRequired:
            self._collection = None
            self.reset_required = True

    @property
    def items(self) -> list[dict[str, Any]]:
        return []

    def reset_collection(self) -> None:
        try:
            from pymilvus import utility
        except Exception as exc:
            raise RuntimeError("Milvus support requires pymilvus. Please install backend requirements.") from exc
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
        self._collection = _create_or_load_collection(
            self.uri,
            self.token,
            self.collection_name,
            self.embedding_dim,
            bm25_enabled=self.bm25_enabled,
        )
        self.reset_required = False

    def delete_document(self, doc_id: str, scope: KnowledgeBaseScope | None = None) -> None:
        self._require_ready()
        scope = scope or _default_scope()
        safe_doc_id = doc_id.replace("\\", "\\\\").replace('"', '\\"')
        self._collection.delete(expr=f'doc_id == "{safe_doc_id}" and {_scope_expr(scope)}')
        flush = getattr(self._collection, "flush", None)
        if callable(flush):
            flush()

    def replace_document_chunks(
        self,
        doc_id: str,
        chunks: list[Chunk],
        scope: KnowledgeBaseScope | None = None,
    ) -> None:
        scope = scope or _scope_from_chunks(chunks)
        self.delete_document(doc_id, scope=scope)
        self.upsert_chunks(chunks)

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        self._require_ready()
        indexable = [chunk for chunk in chunks if chunk.chunk_type in {"child", "table", "ocr", "image_ocr", "image_caption"}]
        if not indexable:
            return
        embeddings = self.embedding_provider.embed_batch([chunk.embedding_text for chunk in indexable])
        rows = []
        for idx, chunk in enumerate(indexable):
            row = {
                "id": chunk.id,
                "embedding": embeddings[idx],
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "workspace_id": str(chunk.metadata.get("workspace_id", "default-workspace")),
                "knowledge_base_id": str(chunk.metadata.get("knowledge_base_id", "default-knowledge-base")),
                "parent_id": chunk.parent_id or "",
                "chunk_type": chunk.chunk_type,
                "strategy": chunk.strategy,
                "processing_version": chunk.processing_version,
                "size_unit": chunk.size_unit,
                "image_id": chunk.image_id,
                "storage_key": chunk.storage_key,
                "source_type": str(chunk.metadata.get("source_type", "")),
                "title_path": chunk.title_path,
                "page_start": int(chunk.page_start or 0),
                "page_end": int(chunk.page_end or 0),
            }
            if self.bm25_enabled:
                row["bm25_text"] = chunk.embedding_text
            rows.append(row)
        self._collection.insert(rows)
        self._collection.flush()

    def upsert(self, ids: list[str], docs: list[str], metadatas: list[dict[str, Any]]) -> None:
        raise RuntimeError("Use upsert_chunks with structured Chunk objects")

    def replace_all(self, ids: list[str], docs: list[str], metadatas: list[dict[str, Any]]) -> None:
        raise RuntimeError("Use structured ingest with DocumentChunker and upsert_chunks")

    def query(
        self,
        question: str,
        top_k: int,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        scope = scope or _default_scope()
        self._require_ready()
        if self.count() == 0:
            return []
        query_embedding = self.embedding_provider.embed_text(question)
        result = self._collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k,
            expr=_scope_expr(scope),
            output_fields=[
                "chunk_id", "doc_id", "workspace_id", "knowledge_base_id", "parent_id",
                "chunk_type", "strategy", "processing_version", "size_unit", "image_id",
                "storage_key", "source_type", "title_path", "page_start", "page_end"
            ],
        )
        hits: list[dict[str, Any]] = []
        for hit in (result[0] if result else []):
            entity = getattr(hit, "entity", None)
            metadata = {
                "child_id": _entity_get(entity, "chunk_id"),
                "chunk_id": _entity_get(entity, "chunk_id"),
                "doc_id": _entity_get(entity, "doc_id"),
                "workspace_id": _entity_get(entity, "workspace_id"),
                "knowledge_base_id": _entity_get(entity, "knowledge_base_id"),
                "parent_id": _entity_get(entity, "parent_id"),
                "chunk_type": _entity_get(entity, "chunk_type"),
                "strategy": _entity_get(entity, "strategy"),
                "processing_version": _entity_get(entity, "processing_version"),
                "size_unit": _entity_get(entity, "size_unit"),
                "image_id": _entity_get(entity, "image_id"),
                "storage_key": _entity_get(entity, "storage_key"),
                "source_type": _entity_get(entity, "source_type"),
                "title_path": _entity_get(entity, "title_path"),
                "page_start": _entity_get(entity, "page_start"),
                "page_end": _entity_get(entity, "page_end"),
            }
            score = float(getattr(hit, "score", 0.0))
            hits.append({"content": "", "metadata": metadata, "distance": max(0.0, 1.0 - score), "vector_score": score})
        return hits

    def query_dense(
        self,
        question: str,
        top_k: int,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        return self.query(question, top_k, scope=scope)

    def search_dense(
        self,
        question: str,
        top_k: int,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        return self.query_dense(question, top_k, scope=scope)

    def query_bm25(
        self,
        question: str,
        top_k: int,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        scope = scope or _default_scope()
        self._require_ready()
        if not self.bm25_enabled:
            return []
        if self.count() == 0:
            return []
        result = self._collection.search(
            data=[question],
            anns_field="bm25_sparse",
            param={"metric_type": "BM25", "params": {}},
            limit=top_k,
            expr=_scope_expr(scope),
            output_fields=[
                "chunk_id", "doc_id", "workspace_id", "knowledge_base_id", "parent_id",
                "chunk_type", "strategy", "processing_version", "size_unit", "image_id",
                "storage_key", "source_type", "title_path", "page_start", "page_end"
            ],
        )
        hits: list[dict[str, Any]] = []
        for hit in (result[0] if result else []):
            entity = getattr(hit, "entity", None)
            metadata = {
                "child_id": _entity_get(entity, "chunk_id"),
                "chunk_id": _entity_get(entity, "chunk_id"),
                "doc_id": _entity_get(entity, "doc_id"),
                "workspace_id": _entity_get(entity, "workspace_id"),
                "knowledge_base_id": _entity_get(entity, "knowledge_base_id"),
                "parent_id": _entity_get(entity, "parent_id"),
                "chunk_type": _entity_get(entity, "chunk_type"),
                "strategy": _entity_get(entity, "strategy"),
                "processing_version": _entity_get(entity, "processing_version"),
                "size_unit": _entity_get(entity, "size_unit"),
                "image_id": _entity_get(entity, "image_id"),
                "storage_key": _entity_get(entity, "storage_key"),
                "source_type": _entity_get(entity, "source_type"),
                "title_path": _entity_get(entity, "title_path"),
                "page_start": _entity_get(entity, "page_start"),
                "page_end": _entity_get(entity, "page_end"),
            }
            score = float(getattr(hit, "score", 0.0))
            hits.append({"content": "", "metadata": metadata, "distance": max(0.0, 1.0 - score), "bm25_score": score})
        return hits

    def search_bm25(
        self,
        question: str,
        top_k: int,
        scope: KnowledgeBaseScope | None = None,
    ) -> list[dict[str, Any]]:
        return self.query_bm25(question, top_k, scope=scope)

    def delete_knowledge_base(self, scope: KnowledgeBaseScope) -> None:
        self._require_ready()
        self._collection.delete(expr=_scope_expr(scope))
        flush = getattr(self._collection, "flush", None)
        if callable(flush):
            flush()

    def count(self) -> int:
        if self._collection is None:
            return 0
        value = getattr(self._collection, "num_entities", 0)
        return int(value() if callable(value) else value)

    def _require_ready(self) -> None:
        if self._collection is None or self.reset_required:
            raise MilvusSchemaResetRequired(
                "Milvus storage requires clean-rebuild before normal reads or writes"
            )


def _entity_get(entity: Any, field: str) -> Any:
    if entity is None:
        return ""
    if hasattr(entity, "get"):
        return entity.get(field)
    return getattr(entity, field, "")


def _default_scope() -> KnowledgeBaseScope:
    return KnowledgeBaseScope(
        workspace_id="default-workspace",
        selected_knowledge_base_ids=("default-knowledge-base",),
        compatibility_default=True,
    )


def _scope_from_chunks(chunks: list[Chunk]) -> KnowledgeBaseScope:
    if not chunks:
        return _default_scope()
    workspace_ids = {str(chunk.metadata.get("workspace_id", "default-workspace")) for chunk in chunks}
    knowledge_base_ids = {str(chunk.metadata.get("knowledge_base_id", "default-knowledge-base")) for chunk in chunks}
    if len(workspace_ids) != 1 or len(knowledge_base_ids) != 1:
        raise ValueError("Vector upsert chunks must share one knowledge base scope")
    return KnowledgeBaseScope(
        workspace_id=next(iter(workspace_ids)),
        selected_knowledge_base_ids=(next(iter(knowledge_base_ids)),),
    )


def _scope_expr(scope: KnowledgeBaseScope) -> str:
    workspace_id = scope.workspace_id.replace("\\", "\\\\").replace('"', '\\"')
    knowledge_base_ids = [item.replace("\\", "\\\\").replace('"', '\\"') for item in scope.selected_knowledge_base_ids]
    kb_ids = ", ".join(f'"{item}"' for item in knowledge_base_ids)
    expr = f'workspace_id == "{workspace_id}" and knowledge_base_id in [{kb_ids}]'
    if scope.document_ids:
        document_ids = [item.replace("\\", "\\\\").replace('"', '\\"') for item in scope.document_ids]
        doc_ids = ", ".join(f'"{item}"' for item in document_ids)
        expr = f"{expr} and doc_id in [{doc_ids}]"
    return expr


VectorStore = MilvusVectorStore
