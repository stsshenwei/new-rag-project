import unittest


class AgenticModelsRouterPlannerTests(unittest.TestCase):
    def test_agent_models_serialize_with_safe_defaults(self):
        from app.models.agentic_retrieval import (
            AgenticRetrievalConfig,
            AgentTraceStep,
            PlannedTool,
            QueryRoute,
            RetrievalPlan,
            TOOL_GRAPH_RETRIEVER,
            TOOL_RAW_RAG,
        )
        from app.schemas import RagQueryResponse

        route = QueryRoute(question_type="fact", detected_entities=["Redis"])
        plan = RetrievalPlan(question_type=route.question_type, tools=[PlannedTool(name=TOOL_RAW_RAG)])
        trace = AgentTraceStep(stage="AnalyzeQuestion", status="completed", summary="Classified as fact.")

        self.assertEqual("fact", route.to_dict()["question_type"])
        self.assertEqual(TOOL_RAW_RAG, plan.to_dict()["tools"][0]["name"])
        self.assertNotIn("chain_of_thought", trace.to_dict())
        self.assertFalse(AgenticRetrievalConfig().enabled)
        self.assertEqual(6, AgenticRetrievalConfig().max_tool_calls)

        response = RagQueryResponse(answer="ok")
        payload = response.model_dump()
        self.assertEqual([], payload["agent_trace"])
        self.assertEqual([], payload["tool_calls"])
        self.assertEqual({}, payload["evidence_summary"])
        self.assertIn("debug_info", payload)
        self.assertEqual(TOOL_GRAPH_RETRIEVER, TOOL_GRAPH_RETRIEVER)

    def test_query_router_classifies_supported_question_types_and_fallback(self):
        from app.services.agent.query_router import QueryRouter

        router = QueryRouter()
        cases = {
            "What is Redis?": "fact",
            "Which source says Redis uses port 6379?": "source",
            "How do I configure Redis timeout?": "howto",
            "Error ERR42 when service cannot connect to Redis": "troubleshooting",
            "Compare Redis and PostgreSQL": "comparison",
            "What is impacted if Redis is unavailable?": "impact",
            "Does API Gateway depend on Auth Service?": "dependency",
            "Summarize the Redis deployment guide": "summary",
            "Should we choose Redis or PostgreSQL?": "decision",
            "我现在需要一个能接28个分光器的OLT，帮我选一款": "decision",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                route = router.route(question)
                self.assertEqual(expected, route.question_type)
                self.assertIn("uncertainty", route.metadata)

        fallback = router.route("")
        self.assertEqual("fact", fallback.question_type)
        self.assertTrue(fallback.metadata["fallback"])

    def test_retrieval_planner_uses_only_approved_tools_and_required_graph_rules(self):
        from app.models.agentic_retrieval import TOOL_GRAPH_RETRIEVER, TOOL_KEYWORD_SEARCH, TOOL_RAW_RAG, QueryRoute
        from app.services.agent.retrieval_planner import RetrievalPlanner

        planner = RetrievalPlanner()

        fact = planner.plan(QueryRoute(question_type="fact"))
        self.assertEqual([TOOL_RAW_RAG, TOOL_GRAPH_RETRIEVER], [tool.name for tool in fact.tools])
        self.assertEqual("entity_search", fact.tools[1].action)

        source = planner.plan(QueryRoute(question_type="source"))
        self.assertEqual([TOOL_RAW_RAG], [tool.name for tool in source.tools])

        dependency = planner.plan(QueryRoute(question_type="dependency", detected_entities=["API", "DB"]))
        self.assertEqual(TOOL_GRAPH_RETRIEVER, dependency.tools[0].name)
        self.assertEqual("path_search", dependency.tools[0].action)
        self.assertTrue(dependency.tools[0].required)

        troubleshooting = planner.plan(QueryRoute(question_type="troubleshooting"))
        self.assertEqual(
            [TOOL_GRAPH_RETRIEVER, TOOL_RAW_RAG, TOOL_KEYWORD_SEARCH],
            [tool.name for tool in troubleshooting.tools],
        )
        self.assertLessEqual(len(troubleshooting.tools), troubleshooting.max_tool_calls)
        self.assertTrue(
            all(tool.name in {TOOL_RAW_RAG, TOOL_KEYWORD_SEARCH, TOOL_GRAPH_RETRIEVER} for tool in troubleshooting.tools)
        )

        decision = planner.plan(QueryRoute(question_type="decision"))
        self.assertEqual([TOOL_RAW_RAG, TOOL_KEYWORD_SEARCH], [tool.name for tool in decision.tools])


if __name__ == "__main__":
    unittest.main()
