from __future__ import annotations

from app.models.agentic_retrieval import (
    APPROVED_TOOLS,
    TOOL_GRAPH_RETRIEVER,
    TOOL_KEYWORD_SEARCH,
    TOOL_RAW_RAG,
    AgenticRetrievalConfig,
    PlannedTool,
    QueryRoute,
    RetrievalPlan,
)


class RetrievalPlanner:
    def __init__(self, config: AgenticRetrievalConfig | None = None):
        self.config = config or AgenticRetrievalConfig()

    def plan(self, route: QueryRoute) -> RetrievalPlan:
        qtype = route.question_type
        graph_limits = {"top_k": self.config.graph_top_k, "max_depth": self.config.graph_max_depth}
        raw_limits = {"top_k": self.config.raw_top_k}
        keyword_limits = {"top_k": self.config.keyword_top_k}

        if qtype == "source":
            tools = [PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits)]
        elif qtype == "dependency":
            tools = [
                PlannedTool(name=TOOL_GRAPH_RETRIEVER, action="path_search", required=True, limits=graph_limits),
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
            ]
        elif qtype == "impact":
            tools = [
                PlannedTool(name=TOOL_GRAPH_RETRIEVER, action="neighbor_search", required=True, limits=graph_limits),
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
            ]
        elif qtype == "troubleshooting":
            tools = [
                PlannedTool(
                    name=TOOL_GRAPH_RETRIEVER,
                    action="entity_search",
                    limits={**graph_limits, "node_types": ["Error", "Config", "Service"]},
                ),
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
                PlannedTool(name=TOOL_KEYWORD_SEARCH, action="search", limits=keyword_limits),
            ]
        elif qtype == "comparison":
            tools = [
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
                PlannedTool(name=TOOL_GRAPH_RETRIEVER, action="entity_search", limits=graph_limits),
            ]
        elif qtype == "howto":
            tools = [
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
                PlannedTool(name=TOOL_KEYWORD_SEARCH, action="search", limits=keyword_limits),
            ]
        elif qtype == "decision":
            tools = [
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
                PlannedTool(name=TOOL_KEYWORD_SEARCH, action="search", limits=keyword_limits),
            ]
        else:
            tools = [
                PlannedTool(name=TOOL_RAW_RAG, action="search", limits=raw_limits),
                PlannedTool(name=TOOL_GRAPH_RETRIEVER, action="entity_search", limits=graph_limits),
            ]

        approved = [tool for tool in tools if tool.name in APPROVED_TOOLS]
        return RetrievalPlan(
            question_type=qtype,
            tools=approved[: self.config.max_tool_calls],
            max_tool_calls=self.config.max_tool_calls,
            metadata={"route": route.to_dict()},
        )
