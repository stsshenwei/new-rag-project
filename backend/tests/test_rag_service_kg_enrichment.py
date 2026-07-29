import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.models.document_models import Chunk, ParsedDocument, ParsedElement
from app.models.kg_models import Entity, KGExtractionResult, Relation
from app.services.documents.document_chunker import DocumentChunker
from app.services.documents.document_repository import DocumentRepository
from app.services.kg.kg_repository import KGRepository
from app.services.kg.kg_service import KGEnrichmentService
from app.services.retrieval.rag_service import RAGService


class FakeVectorStore:
    def __init__(self, persist_dir):
        self.persist_dir = Path(persist_dir)
        self.upserted = []
        self.deleted = []

    def count(self):
        return len(self.upserted)

    def replace_document_chunks(self, doc_id, chunks):
        self.deleted.append(doc_id)
        self.upserted.extend(chunks)

    def upsert_chunks(self, chunks):
        self.upserted.extend(chunks)

    def delete_document(self, doc_id):
        self.deleted.append(doc_id)

    def query_dense(self, question, top_k):
        return []

    def query(self, question, top_k):
        return []


class FakeParser:
    def parse(self, file_path):
        return ParsedDocument(
            doc_id="doc-1",
            file_name=Path(file_path).name,
            file_type="md",
            elements=[
                ParsedElement(
                    element_id="el-1",
                    type="paragraph",
                    text="Service A depends on Redis.",
                    markdown="Service A depends on Redis.",
                    html="",
                    page_start=1,
                    page_end=1,
                    level=None,
                    title_path="Architecture",
                    metadata={},
                )
            ],
        )


class FakeExtractor:
    extractor_version = "kg-v1"

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def extract(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return KGExtractionResult(
            entities=[
                Entity(id="", type="Service", name="Service A", confidence=0.9),
                Entity(id="", type="Middleware", name="Redis", aliases=["redis-server"], confidence=0.9),
            ],
            relations=[
                Relation(
                    source_entity_id="Service A",
                    target_entity_id="Redis",
                    relation_type="DEPENDS_ON",
                    description="Service A depends on Redis",
                    confidence=0.8,
                    source_chunk_id=kwargs["chunk_id"],
                    doc_id=kwargs["doc_id"],
                    page_start=kwargs["page_start"],
                    extractor_version="kg-v1",
                )
            ],
        )


class FakeEntityVectorProvider:
    def __init__(self):
        self.entities = []

    def upsert_entities(self, entities):
        self.entities.extend(entities)

    def search_similar(self, entity, top_k=3):
        return []


class FakeGraphStore:
    def __init__(self, error=None):
        self.error = error
        self.entities = []
        self.relations = []

    def upsert_entity(self, entity):
        if self.error:
            raise self.error
        self.entities.append(entity)

    def upsert_relation(self, relation):
        if self.error:
            raise self.error
        self.relations.append(relation)


class RAGServiceKGEnrichmentTests(unittest.TestCase):
    def make_service(self, tmp, kg_service=None, kg_enabled=False):
        return RAGService(
            vector_store=FakeVectorStore(Path(tmp) / "vector"),
            llm_client=SimpleNamespace(),
            chat_model="test",
            system_prompt="test",
            data_dir=str(Path(tmp) / "data"),
            top_k=3,
            min_relevance_score=0.0,
            chunk_size=80,
            chunk_overlap=10,
            document_repository=DocumentRepository(Path(tmp) / "metadata.sqlite3"),
            document_parser=FakeParser(),
            document_chunker=DocumentChunker(parent_max_tokens=2400, child_max_tokens=80, child_overlap_tokens=10),
            kg_service=kg_service,
            kg_extraction_enabled=kg_enabled,
        )

    def test_kg_disabled_does_not_create_extraction_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            source = data_dir / "manual.md"
            source.write_text("Service A depends on Redis.", encoding="utf-8")
            kg_repo = KGRepository(Path(tmp) / "metadata.sqlite3")
            kg_service = KGEnrichmentService(repository=kg_repo, extractor=FakeExtractor())
            service = self.make_service(tmp, kg_service=kg_service, kg_enabled=False)

            result = service.parse_and_index_document(source)

            self.assertEqual("doc-1", result["doc_id"])
            self.assertEqual([], kg_repo.list_extraction_tasks("doc-1"))

    def test_kg_enabled_persists_mentions_vectors_and_graph_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            source = data_dir / "manual.md"
            source.write_text("Service A depends on Redis.", encoding="utf-8")
            kg_repo = KGRepository(Path(tmp) / "metadata.sqlite3")
            vector = FakeEntityVectorProvider()
            graph = FakeGraphStore()
            kg_service = KGEnrichmentService(repository=kg_repo, extractor=FakeExtractor(), entity_vector_provider=vector, graph_store=graph)
            service = self.make_service(tmp, kg_service=kg_service, kg_enabled=True)

            result = service.parse_and_index_document(source)

            tasks = kg_repo.list_extraction_tasks("doc-1")
            mentions = kg_repo.list_entity_mentions(doc_id="doc-1")
            self.assertEqual("doc-1", result["doc_id"])
            self.assertEqual("completed", tasks[0]["status"])
            self.assertEqual({"Service A", "Redis"}, {mention["entity_name"] for mention in mentions})
            self.assertEqual(2, len(vector.entities))
            self.assertEqual("DEPENDS_ON", graph.relations[0].relation_type)
            self.assertEqual("doc-1", graph.relations[0].doc_id)

    def test_kg_failure_marks_task_failed_without_failing_raw_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            source = data_dir / "manual.md"
            source.write_text("Service A depends on Redis.", encoding="utf-8")
            kg_repo = KGRepository(Path(tmp) / "metadata.sqlite3")
            kg_service = KGEnrichmentService(repository=kg_repo, extractor=FakeExtractor(error=RuntimeError("extract failed")))
            service = self.make_service(tmp, kg_service=kg_service, kg_enabled=True)

            result = service.parse_and_index_document(source)

            tasks = kg_repo.list_extraction_tasks("doc-1")
            self.assertEqual("doc-1", result["doc_id"])
            self.assertEqual("failed", tasks[0]["status"])
            self.assertIn("extract failed", tasks[0]["error_message"])
            self.assertGreater(service.document_repository.count_chunks({"child"}), 0)


if __name__ == "__main__":
    unittest.main()
