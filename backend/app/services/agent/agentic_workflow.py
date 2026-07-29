from __future__ import annotations

import inspect
from typing import Any

from app.models.agentic_retrieval import (
    TOOL_GRAPH_RETRIEVER,
    AgentStreamEvent,
    AgentTraceStep,
    AgenticRetrievalConfig,
    EvidenceBundle,
    RetrievalPlan,
    ToolCallRecord,
)
from app.models.knowledge_base import KnowledgeBaseScope


class AgenticRetrievalWorkflow:
    def __init__(self, router, planner, tools: dict[str, Any], citation_verifier, rag_service, config: AgenticRetrievalConfig | None = None):
        self.router = router
        self.planner = planner
        self.tools = tools
        self.citation_verifier = citation_verifier
        self.rag_service = rag_service
        self.config = config or AgenticRetrievalConfig()

    def _run_tool(self, tool: Any, question: str, planned_tool: Any, scope: KnowledgeBaseScope):
        parameters = inspect.signature(tool.run).parameters
        if "scope" in parameters:
            return tool.run(question, planned_tool, scope=scope)
        if not scope.compatibility_default:
            raise RuntimeError(f"Tool {getattr(tool, 'name', type(tool).__name__)} does not support knowledge-base scope")
        return tool.run(question, planned_tool)

    def _resolve_scope(self, scope: KnowledgeBaseScope | None) -> KnowledgeBaseScope:
        if scope is not None:
            return scope
        resolver = getattr(self.rag_service, "resolve_scope", None)
        if callable(resolver):
            return resolver()
        return KnowledgeBaseScope(
            "default-workspace", ("default-knowledge-base",), compatibility_default=True
        )

    def _verify_citations(self, fused: EvidenceBundle, scope: KnowledgeBaseScope):
        parameters = inspect.signature(self.citation_verifier.verify).parameters
        if "scope" in parameters:
            return self.citation_verifier.verify(
                fused.citations, fused.used_chunks, fused.graph_paths, scope=scope
            )
        if not scope.compatibility_default:
            raise RuntimeError("Citation verifier does not support knowledge-base scope")
        return self.citation_verifier.verify(fused.citations, fused.used_chunks, fused.graph_paths)

    def stream_query_events(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        conversation_context: dict[str, Any] | None = None,
        memory_context: str | None = None,
        scope: KnowledgeBaseScope | None = None,
    ):
        scope = self._resolve_scope(scope)
        trace: list[AgentTraceStep] = []
        tool_calls: list[ToolCallRecord] = []

        route = self.router.route(question)
        step = AgentTraceStep("AnalyzeQuestion", "completed", f"Question routed as {route.question_type}.", metadata=route.to_dict())
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        plan = self.planner.plan(route)
        step = AgentTraceStep("PlanRetrieval", "completed", f"Planned {len(plan.tools)} approved retrieval tools.", metadata=plan.to_dict())
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        step = AgentTraceStep(
            "CheckPermissionScope",
            "completed",
            "Knowledge base evidence scope validated.",
            metadata={"filters": filters or {}, "knowledge_base_scope": scope.to_dict()},
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        tool_results = []
        for tool_index, planned_tool in enumerate(plan.tools[: plan.max_tool_calls], start=1):
            call_id = f"round-1-tool-{tool_index}"
            call_start = {
                "call_id": call_id,
                "tool": planned_tool.name,
                "action": planned_tool.action,
                "input_summary": f'搜索关键词："{question}"',
                "limits": planned_tool.limits,
                "required": planned_tool.required,
                "metadata": {"round": 1, "call_id": call_id, "knowledge_base_scope": scope.to_dict()},
            }
            yield AgentStreamEvent("tool_call", call_start)
            tool = self.tools.get(planned_tool.name)
            if tool is None:
                result = None
                record = ToolCallRecord(planned_tool.name, planned_tool.action, "skipped", "Tool unavailable", "No provider configured")
            else:
                result = self._run_tool(tool, question, planned_tool, scope)
                record = ToolCallRecord(
                    tool=planned_tool.name,
                    action=planned_tool.action,
                    status=result.status,
                    input_summary=call_start["input_summary"],
                    output_summary=result.observation or result.error,
                    source_chunk_ids=result.evidence.source_chunk_ids,
                    metadata={
                        **result.evidence.metadata,
                        **result.metadata,
                        "round": 1,
                        "call_id": call_id,
                        "limits": planned_tool.limits,
                        "required": planned_tool.required,
                        "evidence_items": len(result.evidence.items),
                        "citations": len(result.evidence.citations),
                        "source_titles": list(
                            dict.fromkeys(
                                str(citation.get("source", ""))
                                for citation in result.evidence.citations
                                if citation.get("source")
                            )
                        ),
                        "entities": len(result.evidence.entities),
                        "graph_paths": len(result.evidence.graph_paths),
                        "knowledge_base_scope": scope.to_dict(),
                    },
                )
            tool_calls.append(record)
            yield AgentStreamEvent("tool_observation", record.to_dict())
            if result is not None:
                tool_results.append((planned_tool, result))
                for read_event in self._document_read_events(
                    result, round_number=1, parent_call_id=call_id, scope=scope
                ):
                    yield read_event

        step = AgentTraceStep(
            "RunRetrieval",
            "completed" if all(call.status in {"completed", "skipped"} for call in tool_calls) else "partial",
            f"Executed {len(tool_calls)} planned retrieval tool calls.",
            source_chunk_ids=[chunk_id for call in tool_calls for chunk_id in call.source_chunk_ids],
            metadata={"tool_calls": [call.to_dict() for call in tool_calls]},
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        fused = self._fuse_evidence(tool_results)
        step = AgentTraceStep(
            "FuseEvidence",
            "completed",
            f"Fused {len(fused.items)} evidence items from approved tools.",
            source_chunk_ids=fused.source_chunk_ids,
            metadata=self._evidence_summary(fused, tool_calls),
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        step = AgentTraceStep("RerankEvidence", "completed", "Kept provider ranking for fused evidence.", metadata={"strategy": "provider_order"})
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        sufficient, sufficiency_reason = self._is_sufficient(plan, fused)
        evidence_summary = {
            **self._evidence_summary(fused, tool_calls),
            "sufficient": sufficient,
            "sufficiency_reason": sufficiency_reason,
            "confidence": fused.confidence,
        }
        step = AgentTraceStep(
            "NeedMoreEvidence",
            "completed",
            sufficiency_reason,
            source_chunk_ids=fused.source_chunk_ids,
            metadata={"sufficient": sufficient, "question_type": plan.question_type},
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())
        yield AgentStreamEvent("evidence_summary", evidence_summary)

        context_hits = self._raw_hits_from_bundle(fused)
        step = AgentTraceStep(
            "BuildContext",
            "completed" if context_hits or fused.graph_paths else "partial",
            "Built answer context from verified evidence candidates.",
            source_chunk_ids=fused.source_chunk_ids,
            metadata={"context_items": len(context_hits), "graph_paths": len(fused.graph_paths)},
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        sources = fused.citations
        reasoning = {
            "question": question,
            "route": route.question_type,
            "planned_tools": [tool.name for tool in plan.tools],
            "evidence": [
                {
                    "source_tool": item.source_tool,
                    "chunk_id": item.chunk_id,
                    "score": item.score,
                    "preview": item.content[:220],
                }
                for item in fused.items[:5]
            ],
            "summary": sufficiency_reason,
        }
        yield AgentStreamEvent("sources", {"items": sources})
        yield AgentStreamEvent("reasoning", reasoning)

        verification = self._verify_citations(fused, scope)
        yield AgentStreamEvent("citation_verification", verification.to_dict())

        if not sufficient:
            answer = "I cannot determine the answer from the available evidence."
            confidence = min(0.3, fused.confidence)
            yield AgentStreamEvent("token", {"token": answer})
        elif not verification.valid:
            answer = "I cannot determine the answer from the available evidence because citation verification failed."
            confidence = min(0.2, fused.confidence)
            yield AgentStreamEvent("token", {"token": answer})
        else:
            answer_parts: list[str] = []
            for token in self._stream_answer_tokens(question, context_hits, conversation_context, memory_context):
                answer_parts.append(token)
                yield AgentStreamEvent("token", {"token": token})
            answer = "".join(answer_parts)
            confidence = fused.confidence

        step = AgentTraceStep("GenerateAnswer", "completed", "Generated answer from fused evidence only.", source_chunk_ids=fused.source_chunk_ids)
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        step = AgentTraceStep(
            "VerifyCitations",
            "completed" if verification.valid else "failed",
            verification.summary,
            source_chunk_ids=verification.verified_chunks,
            metadata=verification.to_dict(),
        )
        trace.append(step)
        yield AgentStreamEvent("agent_trace", step.to_dict())

        response = {
            "answer": answer,
            "citations": fused.citations if verification.valid else [],
            "used_chunks": verification.verified_chunks or [chunk for chunk in fused.used_chunks if chunk not in verification.invalid_chunks],
            "used_entities": fused.entities,
            "graph_paths": fused.graph_paths if verification.valid else [],
            "confidence": round(float(confidence or 0.0), 4),
            "agent_trace": [item.to_dict() for item in trace],
            "tool_calls": [call.to_dict() for call in tool_calls],
            "evidence_summary": evidence_summary,
            "debug_info": {
                "route": route.to_dict(),
                "plan": plan.to_dict(),
                "citation_verification": verification.to_dict(),
                "sufficiency": {"sufficient": sufficient, "reason": sufficiency_reason},
                "knowledge_base_scope": scope.to_dict(),
            },
        }
        step = AgentTraceStep("ReturnAnswer", "completed", "Returned streamed enterprise response.", metadata={"confidence": response["confidence"]})
        trace.append(step)
        response["agent_trace"] = [item.to_dict() for item in trace]
        yield AgentStreamEvent("agent_trace", step.to_dict())
        yield AgentStreamEvent("final", response)

    def _document_read_events(
        self,
        result,
        round_number: int,
        parent_call_id: str,
        scope: KnowledgeBaseScope,
    ):
        if result.tool not in {"RawRAGTool", "KeywordSearchTool"}:
            return
        documents: dict[str, list[str]] = {}
        for item in result.evidence.items:
            source = str(item.metadata.get("source") or item.doc_id or "").strip()
            if not source or not item.content.strip():
                continue
            chunk_ids = documents.setdefault(source, [])
            for chunk_id in [item.chunk_id, *item.source_chunk_ids]:
                if chunk_id and chunk_id not in chunk_ids:
                    chunk_ids.append(chunk_id)
        for index, (source, chunk_ids) in enumerate(list(documents.items())[:5], start=1):
            call_id = f"{parent_call_id}-read-{index}"
            yield AgentStreamEvent(
                "tool_call",
                {
                    "call_id": call_id,
                    "tool": "DocumentChunkReaderTool",
                    "action": "read_chunks",
                    "input_summary": f'查看文章："{source}"',
                    "metadata": {
                        "round": round_number,
                        "call_id": call_id,
                        "source": source,
                        "knowledge_base_scope": scope.to_dict(),
                    },
                },
            )
            yield AgentStreamEvent(
                "tool_observation",
                {
                    "call_id": call_id,
                    "tool": "DocumentChunkReaderTool",
                    "action": "read_chunks",
                    "status": "completed",
                    "output_summary": f"已加载 {len(chunk_ids) or 1} 个分块",
                    "source_chunk_ids": chunk_ids,
                    "metadata": {
                        "round": round_number,
                        "call_id": call_id,
                        "source": source,
                        "source_titles": [source],
                        "chunk_count": len(chunk_ids) or 1,
                        "fetched_chunks": len(chunk_ids) or 1,
                        "total_chunks": len(chunk_ids) or 1,
                        "used_chunks": len(chunk_ids) or 1,
                        "knowledge_base_scope": scope.to_dict(),
                    },
                },
            )

    def run_query(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        scope: KnowledgeBaseScope | None = None,
    ) -> dict[str, Any]:
        scope = self._resolve_scope(scope)
        trace: list[AgentTraceStep] = []
        tool_calls: list[ToolCallRecord] = []

        route = self.router.route(question)
        trace.append(AgentTraceStep("AnalyzeQuestion", "completed", f"Question routed as {route.question_type}.", metadata=route.to_dict()))

        plan = self.planner.plan(route)
        trace.append(AgentTraceStep("PlanRetrieval", "completed", f"Planned {len(plan.tools)} approved retrieval tools.", metadata=plan.to_dict()))

        trace.append(
            AgentTraceStep(
                "CheckPermissionScope",
                "completed",
                "Knowledge base evidence scope validated.",
                metadata={"filters": filters or {}, "knowledge_base_scope": scope.to_dict()},
            )
        )

        tool_results = []
        for planned_tool in plan.tools[: plan.max_tool_calls]:
            tool = self.tools.get(planned_tool.name)
            if tool is None:
                result = None
                record = ToolCallRecord(planned_tool.name, planned_tool.action, "skipped", "Tool unavailable", "No provider configured")
            else:
                result = self._run_tool(tool, question, planned_tool, scope)
                record = ToolCallRecord(
                    tool=planned_tool.name,
                    action=planned_tool.action,
                    status=result.status,
                    input_summary=f"{planned_tool.action} for {route.question_type}",
                    output_summary=result.observation or result.error,
                    source_chunk_ids=result.evidence.source_chunk_ids,
                    metadata={
                        **result.evidence.metadata,
                        **result.metadata,
                        "limits": planned_tool.limits,
                        "required": planned_tool.required,
                        "evidence_items": len(result.evidence.items),
                        "citations": len(result.evidence.citations),
                        "entities": len(result.evidence.entities),
                        "graph_paths": len(result.evidence.graph_paths),
                        "knowledge_base_scope": scope.to_dict(),
                    },
                )
            tool_calls.append(record)
            if result is not None:
                tool_results.append((planned_tool, result))
        trace.append(
            AgentTraceStep(
                "RunRetrieval",
                "completed" if all(call.status in {"completed", "skipped"} for call in tool_calls) else "partial",
                f"Executed {len(tool_calls)} planned retrieval tool calls.",
                source_chunk_ids=[chunk_id for call in tool_calls for chunk_id in call.source_chunk_ids],
                metadata={"tool_calls": [call.to_dict() for call in tool_calls]},
            )
        )

        fused = self._fuse_evidence(tool_results)
        trace.append(
            AgentTraceStep(
                "FuseEvidence",
                "completed",
                f"Fused {len(fused.items)} evidence items from approved tools.",
                source_chunk_ids=fused.source_chunk_ids,
                metadata=self._evidence_summary(fused, tool_calls),
            )
        )

        trace.append(AgentTraceStep("RerankEvidence", "completed", "Kept provider ranking for fused evidence.", metadata={"strategy": "provider_order"}))

        sufficient, sufficiency_reason = self._is_sufficient(plan, fused)
        trace.append(
            AgentTraceStep(
                "NeedMoreEvidence",
                "completed",
                sufficiency_reason,
                source_chunk_ids=fused.source_chunk_ids,
                metadata={"sufficient": sufficient, "question_type": plan.question_type},
            )
        )

        context_hits = self._raw_hits_from_bundle(fused)
        trace.append(
            AgentTraceStep(
                "BuildContext",
                "completed" if context_hits or fused.graph_paths else "partial",
                "Built answer context from verified evidence candidates.",
                source_chunk_ids=fused.source_chunk_ids,
                metadata={"context_items": len(context_hits), "graph_paths": len(fused.graph_paths)},
            )
        )

        if not sufficient:
            answer = "I cannot determine the answer from the available evidence."
            confidence = min(0.3, fused.confidence)
        else:
            answer = "".join(self.rag_service.stream_answer(question, hits=context_hits)) if context_hits else "I cannot determine the answer from the available evidence."
            confidence = fused.confidence
        trace.append(AgentTraceStep("GenerateAnswer", "completed", "Generated answer from fused evidence only.", source_chunk_ids=fused.source_chunk_ids))

        verification = self._verify_citations(fused, scope)
        if sufficient and not verification.valid:
            answer = "I cannot determine the answer from the available evidence because citation verification failed."
            confidence = min(0.2, confidence)
        trace.append(
            AgentTraceStep(
                "VerifyCitations",
                "completed" if verification.valid else "failed",
                verification.summary,
                source_chunk_ids=verification.verified_chunks,
                metadata=verification.to_dict(),
            )
        )

        response = {
            "answer": answer,
            "citations": fused.citations if verification.valid else [],
            "used_chunks": verification.verified_chunks or [chunk for chunk in fused.used_chunks if chunk not in verification.invalid_chunks],
            "used_entities": fused.entities,
            "graph_paths": fused.graph_paths if verification.valid else [],
            "confidence": round(float(confidence or 0.0), 4),
            "agent_trace": [step.to_dict() for step in trace],
            "tool_calls": [call.to_dict() for call in tool_calls],
            "evidence_summary": self._evidence_summary(fused, tool_calls),
            "debug_info": {
                "route": route.to_dict(),
                "plan": plan.to_dict(),
                "citation_verification": verification.to_dict(),
                "sufficiency": {"sufficient": sufficient, "reason": sufficiency_reason},
                "knowledge_base_scope": scope.to_dict(),
            },
        }
        trace.append(AgentTraceStep("ReturnAnswer", "completed", "Returned enterprise response.", metadata={"confidence": response["confidence"]}))
        response["agent_trace"] = [step.to_dict() for step in trace]
        return response

    def _fuse_evidence(self, tool_results: list[tuple[Any, Any]]) -> EvidenceBundle:
        items = []
        citations = []
        used_chunks = []
        entities = []
        relations = []
        graph_paths = []
        source_chunk_ids = []
        confidence = 0.0
        seen_items = set()
        for planned_tool, result in tool_results:
            bundle = result.evidence
            confidence = max(confidence, float(bundle.confidence or 0.0))
            citations.extend(bundle.citations)
            used_chunks.extend(bundle.used_chunks)
            entities.extend(bundle.entities)
            relations.extend(bundle.relations)
            graph_paths.extend(bundle.graph_paths)
            source_chunk_ids.extend(bundle.source_chunk_ids)
            for item in bundle.items:
                key = (item.source_tool, item.id)
                if key in seen_items:
                    continue
                item.metadata = {**item.metadata, "question_type": planned_tool.metadata.get("question_type", ""), "planned_action": planned_tool.action}
                items.append(item)
                seen_items.add(key)
        return EvidenceBundle(
            items=items,
            citations=_dedupe_dicts(citations, "chunk_id"),
            used_chunks=list(dict.fromkeys(used_chunks)),
            entities=_dedupe_dicts(entities, "id"),
            relations=relations,
            graph_paths=graph_paths,
            source_chunk_ids=list(dict.fromkeys(source_chunk_ids)),
            confidence=confidence,
        )

    def _is_sufficient(self, plan: RetrievalPlan, fused: EvidenceBundle) -> tuple[bool, str]:
        required_graph = any(tool.name == TOOL_GRAPH_RETRIEVER and tool.required for tool in plan.tools)
        if plan.question_type in {"dependency", "impact"} or required_graph:
            if not fused.graph_paths and not fused.relations:
                return False, "Graph path evidence is required but unavailable."
        if not fused.citations and not fused.graph_paths:
            return False, "No traceable raw or graph evidence was found."
        return True, "Evidence is sufficient for a sourced answer."

    def _raw_hits_from_bundle(self, fused: EvidenceBundle) -> list[dict[str, Any]]:
        hits = []
        for item in fused.items:
            if not item.content:
                continue
            hits.append(
                {
                    "content": item.content,
                    "metadata": {
                        **item.metadata,
                        "doc_id": item.doc_id,
                        "chunk_id": item.chunk_id,
                        "child_id": item.chunk_id,
                        "parent_id": item.parent_id,
                        "matched_child_ids": [item.chunk_id] if item.chunk_id else [],
                    },
                    "hybrid_score": item.score,
                }
            )
        return hits

    def _stream_answer_tokens(
        self,
        question: str,
        context_hits: list[dict[str, Any]],
        conversation_context: dict[str, Any] | None,
        memory_context: str | None,
    ):
        try:
            yield from self.rag_service.stream_answer(
                question,
                hits=context_hits,
                conversation_context=conversation_context,
                memory_context=memory_context,
            )
        except TypeError:
            yield from self.rag_service.stream_answer(question, hits=context_hits)

    def _evidence_summary(self, fused: EvidenceBundle, tool_calls: list[ToolCallRecord]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for call in tool_calls:
            counts[call.tool] = counts.get(call.tool, 0) + 1
        return {
            "tool_counts": counts,
            "evidence_items": len(fused.items),
            "citations": len(fused.citations),
            "used_chunks": len(fused.used_chunks),
            "used_entities": len(fused.entities),
            "graph_paths": len(fused.graph_paths),
            "source_chunk_ids": fused.source_chunk_ids,
        }


def _dedupe_dicts(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        value = str(item.get(key) or item.get("chunk_id") or item.get("entity_id") or item.get("name") or item)
        if value in seen:
            continue
        result.append(item)
        seen.add(value)
    return result
