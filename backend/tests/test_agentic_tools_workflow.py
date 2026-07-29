import unittest


class FakeDocumentRepository:
    def __init__(self, valid_chunk_ids=None):
        self.valid_chunk_ids = set(valid_chunk_ids or [])

    def get_chunk(self, chunk_id):
        return {"id": chunk_id} if chunk_id in self.valid_chunk_ids else None


class FakeRAGService:
    def __init__(self, valid_chunk_ids=None):
        self.document_repository = FakeDocumentRepository(valid_chunk_ids or {"c1", "p1", "g1"})
        self.generated_with_hits = []

    def hybrid_retrieve_hits(self, question):
        return [
            {
                "content": "Redis is used by API Gateway.",
                "metadata": {
                    "source": "manual.md",
                    "doc_id": "doc-1",
                    "chunk_id": "c1",
                    "child_id": "c1",
                    "parent_id": "p1",
                    "matched_child_ids": ["c1"],
                },
                "hybrid_score": 0.82,
                "distance": 0.18,
            }
        ]

    def recall_parent_hits(self, hits):
        return hits

    def extract_sources(self, hits):
        return [
            {
                "source": "manual.md",
                "score": 0.82,
                "doc_id": "doc-1",
                "chunk_id": "c1",
                "parent_id": "p1",
            }
        ]

    def keyword_retrieve_hits(self, question, top_k=None):
        return [
            {
                "content": "ERR42 timeout caused by Redis config.",
                "metadata": {"source": "manual.md", "doc_id": "doc-1", "chunk_id": "c1", "parent_id": "p1"},
                "keyword_score": 0.7,
            }
        ]

    def stream_answer(self, question, hits=None):
        self.generated_with_hits.append(hits or [])
        yield "Redis is used by API Gateway. [manual.md]"


class InvalidCitationRAGService(FakeRAGService):
    def extract_sources(self, hits):
        return [{"source": "manual.md", "score": 0.82, "doc_id": "doc-1", "chunk_id": "missing"}]


class EmptyGraphRetriever:
    def entity_search(self, question):
        return {"entities": [], "relations": [], "paths": [], "source_chunk_ids": [], "confidence": 0.0}

    def neighbor_search(self, entity_id, depth=1):
        return {"entities": [], "relations": [], "paths": [], "source_chunk_ids": [], "confidence": 0.0}

    def path_search(self, source_entity, target_entity, max_depth=3):
        return {"entities": [], "relations": [], "paths": [], "source_chunk_ids": [], "confidence": 0.0}


class FakeGraphRetriever(EmptyGraphRetriever):
    def entity_search(self, question):
        return {
            "entities": [{"id": "e1", "name": "Redis", "type": "Service"}],
            "relations": [],
            "paths": [],
            "source_chunk_ids": ["g1"],
            "confidence": 0.65,
        }

    def path_search(self, source_entity, target_entity, max_depth=3):
        return {
            "entities": [{"id": "api", "name": source_entity}, {"id": "db", "name": target_entity}],
            "relations": [{"source_chunk_id": "g1", "relation": "DEPENDS_ON"}],
            "paths": [{"nodes": [source_entity, target_entity], "relations": [{"source_chunk_id": "g1"}]}],
            "source_chunk_ids": ["g1"],
            "confidence": 0.71,
        }


class AgenticToolsWorkflowTests(unittest.TestCase):
    def test_tools_return_traceable_evidence_without_generating_answers(self):
        from app.models.agentic_retrieval import PlannedTool
        from app.services.agent.agent_tools import GraphRetrieverTool, KeywordSearchTool, RawRAGTool

        rag = FakeRAGService()
        raw_result = RawRAGTool(rag).run("What is Redis?", PlannedTool(name="RawRAGTool"))
        keyword_result = KeywordSearchTool(rag).run("ERR42 Redis", PlannedTool(name="KeywordSearchTool"))
        graph_result = GraphRetrieverTool(FakeGraphRetriever()).run(
            "Redis", PlannedTool(name="GraphRetrieverTool", action="entity_search")
        )

        self.assertEqual("completed", raw_result.status)
        self.assertEqual("RawRAGTool", raw_result.evidence.items[0].source_tool)
        self.assertEqual(["c1"], raw_result.evidence.source_chunk_ids)
        self.assertEqual("KeywordSearchTool", keyword_result.evidence.items[0].source_tool)
        self.assertEqual(["g1"], graph_result.evidence.source_chunk_ids)
        self.assertEqual([], rag.generated_with_hits)

    def test_workflow_runs_states_and_returns_enterprise_fact_response(self):
        from app.models.agentic_retrieval import AgenticRetrievalConfig
        from app.services.agent.agentic_workflow import AgenticRetrievalWorkflow
        from app.services.agent.agent_tools import GraphRetrieverTool, KeywordSearchTool, RawRAGTool
        from app.services.retrieval.citation_verifier import CitationVerifier
        from app.services.agent.query_router import QueryRouter
        from app.services.agent.retrieval_planner import RetrievalPlanner

        rag = FakeRAGService()
        workflow = AgenticRetrievalWorkflow(
            router=QueryRouter(),
            planner=RetrievalPlanner(),
            tools={
                "RawRAGTool": RawRAGTool(rag),
                "KeywordSearchTool": KeywordSearchTool(rag),
                "GraphRetrieverTool": GraphRetrieverTool(FakeGraphRetriever()),
            },
            citation_verifier=CitationVerifier(rag.document_repository),
            rag_service=rag,
            config=AgenticRetrievalConfig(enabled=True),
        )

        result = workflow.run_query("What is Redis?")
        stages = [step["stage"] for step in result["agent_trace"]]
        self.assertEqual(
            [
                "AnalyzeQuestion",
                "PlanRetrieval",
                "CheckPermissionScope",
                "RunRetrieval",
                "FuseEvidence",
                "RerankEvidence",
                "NeedMoreEvidence",
                "BuildContext",
                "GenerateAnswer",
                "VerifyCitations",
                "ReturnAnswer",
            ],
            stages,
        )
        self.assertEqual("Redis is used by API Gateway. [manual.md]", result["answer"])
        self.assertEqual(["c1"], result["used_chunks"])
        self.assertEqual("Redis", result["used_entities"][0]["name"])
        self.assertIn("tool_counts", result["evidence_summary"])
        self.assertNotIn("chain_of_thought", str(result["agent_trace"]))

    def test_dependency_without_graph_path_returns_explicit_uncertainty(self):
        from app.models.agentic_retrieval import AgenticRetrievalConfig
        from app.services.agent.agentic_workflow import AgenticRetrievalWorkflow
        from app.services.agent.agent_tools import GraphRetrieverTool, KeywordSearchTool, RawRAGTool
        from app.services.retrieval.citation_verifier import CitationVerifier
        from app.services.agent.query_router import QueryRouter
        from app.services.agent.retrieval_planner import RetrievalPlanner

        rag = FakeRAGService()
        workflow = AgenticRetrievalWorkflow(
            router=QueryRouter(),
            planner=RetrievalPlanner(),
            tools={
                "RawRAGTool": RawRAGTool(rag),
                "KeywordSearchTool": KeywordSearchTool(rag),
                "GraphRetrieverTool": GraphRetrieverTool(EmptyGraphRetriever()),
            },
            citation_verifier=CitationVerifier(rag.document_repository),
            rag_service=rag,
            config=AgenticRetrievalConfig(enabled=True),
        )

        result = workflow.run_query("Does API Gateway depend on Redis?")
        self.assertIn("cannot determine", result["answer"])
        self.assertEqual([], result["graph_paths"])
        self.assertLess(result["confidence"], 0.5)

    def test_source_question_uses_raw_only_and_troubleshooting_uses_three_tools(self):
        from app.models.agentic_retrieval import AgenticRetrievalConfig
        from app.services.agent.agentic_workflow import AgenticRetrievalWorkflow
        from app.services.agent.agent_tools import GraphRetrieverTool, KeywordSearchTool, RawRAGTool
        from app.services.retrieval.citation_verifier import CitationVerifier
        from app.services.agent.query_router import QueryRouter
        from app.services.agent.retrieval_planner import RetrievalPlanner

        rag = FakeRAGService()
        workflow = AgenticRetrievalWorkflow(
            router=QueryRouter(),
            planner=RetrievalPlanner(),
            tools={
                "RawRAGTool": RawRAGTool(rag),
                "KeywordSearchTool": KeywordSearchTool(rag),
                "GraphRetrieverTool": GraphRetrieverTool(FakeGraphRetriever()),
            },
            citation_verifier=CitationVerifier(rag.document_repository),
            rag_service=rag,
            config=AgenticRetrievalConfig(enabled=True),
        )

        source_result = workflow.run_query("Which source says Redis is used?")
        self.assertEqual(["RawRAGTool"], [call["tool"] for call in source_result["tool_calls"]])

        troubleshooting_result = workflow.run_query("Error ERR42 when Redis timeout happens")
        self.assertEqual(
            ["GraphRetrieverTool", "RawRAGTool", "KeywordSearchTool"],
            [call["tool"] for call in troubleshooting_result["tool_calls"]],
        )

    def test_invalid_answer_citation_downgrades_fact_response(self):
        from app.models.agentic_retrieval import AgenticRetrievalConfig
        from app.services.agent.agentic_workflow import AgenticRetrievalWorkflow
        from app.services.agent.agent_tools import GraphRetrieverTool, KeywordSearchTool, RawRAGTool
        from app.services.retrieval.citation_verifier import CitationVerifier
        from app.services.agent.query_router import QueryRouter
        from app.services.agent.retrieval_planner import RetrievalPlanner

        rag = InvalidCitationRAGService(valid_chunk_ids={"c1"})
        workflow = AgenticRetrievalWorkflow(
            router=QueryRouter(),
            planner=RetrievalPlanner(),
            tools={
                "RawRAGTool": RawRAGTool(rag),
                "KeywordSearchTool": KeywordSearchTool(rag),
                "GraphRetrieverTool": GraphRetrieverTool(EmptyGraphRetriever()),
            },
            citation_verifier=CitationVerifier(rag.document_repository),
            rag_service=rag,
            config=AgenticRetrievalConfig(enabled=True),
        )

        result = workflow.run_query("What is Redis?")
        self.assertIn("citation verification failed", result["answer"])
        self.assertEqual([], result["citations"])
        self.assertLess(result["confidence"], 0.5)

    def test_citation_verifier_blocks_invalid_citations_and_graph_sources(self):
        from app.services.retrieval.citation_verifier import CitationVerifier

        verifier = CitationVerifier(FakeDocumentRepository(valid_chunk_ids={"c1"}))
        result = verifier.verify(
            citations=[{"chunk_id": "missing"}],
            used_chunks=["c1", "missing-used"],
            graph_paths=[{"relations": [{"source_chunk_id": "missing-graph"}]}],
        )

        self.assertFalse(result.valid)
        self.assertEqual(["missing"], result.invalid_citations)
        self.assertEqual(["missing-used"], result.invalid_chunks)
        self.assertEqual(["missing-graph"], result.invalid_graph_source_chunks)
        self.assertIn("invalid", result.summary)


if __name__ == "__main__":
    unittest.main()
