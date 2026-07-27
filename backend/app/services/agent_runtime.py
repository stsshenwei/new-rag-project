from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Generator
from uuid import uuid4

from app.models.agent_runtime import (
    AgentEventBus,
    AgentEventSequencer,
    AgentRuntimeConfig,
    AgentRuntimeEvent,
    ChatRuntimePolicy,
    RuntimeToolResult,
    agent_event,
    resolve_chat_runtime_policy,
    scrub_private_fields,
    tool_call_to_agent_event,
    tool_result_to_agent_event,
)
from app.models.knowledge_base import KnowledgeBaseScope
from app.services.agent_prompt_templates import (
    AgentPromptCatalog,
    ContextPromptCatalog,
    PromptTemplateCatalog,
    PromptTemplateError,
    scope_to_prompt_kbs,
)
from app.services.agent_runtime_spans import AgentRuntimeSpanRepository
from app.services.agent_runtime_tools import RuntimeToolContext, ToolRegistry
from app.services.logging_config import get_trace_id, sanitize_payload, truncate_text
from app.services.observability import activate_observation, get_observability_sink

logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(
        self,
        *,
        llm_client: Any,
        chat_model: str,
        rag_service: Any,
        prompt_catalog: AgentPromptCatalog,
        tool_registry: ToolRegistry,
        config: AgentRuntimeConfig,
        context_catalog: ContextPromptCatalog | None = None,
        skills_manager: Any | None = None,
        graph_retriever: Any | None = None,
        span_repository: AgentRuntimeSpanRepository | None = None,
    ):
        self.llm_client = llm_client
        self.chat_model = chat_model
        self.rag_service = rag_service
        self.prompt_catalog = prompt_catalog
        self.context_catalog = context_catalog or ContextPromptCatalog.load("config/prompt_templates/context_template.yaml")
        self.tool_registry = tool_registry
        self.config = config
        self.skills_manager = skills_manager
        self.graph_retriever = graph_retriever
        self.span_repository = span_repository or AgentRuntimeSpanRepository.disabled()

    def stream_query_events(
        self,
        question: str,
        *,
        conversation_context: str | dict[str, Any] | None = None,
        memory_context: str | None = None,
        scope: KnowledgeBaseScope | None = None,
        attachments: list[dict[str, Any]] | None = None,
        mode: str = "reasoning",
    ) -> Generator[AgentRuntimeEvent, None, None]:
        yield from self.execute(
            question,
            conversation_context=conversation_context,
            memory_context=memory_context,
            scope=scope,
            attachments=attachments,
            mode=mode,
        )

    def execute(
        self,
        question: str,
        *,
        conversation_context: str | dict[str, Any] | None = None,
        memory_context: str | None = None,
        scope: KnowledgeBaseScope | None = None,
        attachments: list[dict[str, Any]] | None = None,
        mode: str = "reasoning",
    ) -> Generator[AgentRuntimeEvent, None, None]:
        scope = scope or self.rag_service.default_scope
        policy = resolve_chat_runtime_policy(mode, self.config)
        yield from self.execute_loop(
            question,
            policy=policy,
            conversation_context=conversation_context,
            memory_context=memory_context,
            scope=scope,
            attachments=attachments,
        )

    def execute_loop(
        self,
        question: str,
        *,
        policy: ChatRuntimePolicy,
        conversation_context: str | dict[str, Any] | None = None,
        memory_context: str | None = None,
        scope: KnowledgeBaseScope,
        attachments: list[dict[str, Any]] | None = None,
    ) -> Generator[AgentRuntimeEvent, None, None]:
        run_id = uuid4().hex
        event_sequence = AgentEventSequencer()
        event_bus = AgentEventBus()
        run_started = time.time()
        trace: list[dict[str, Any]] = []
        tool_events: list[dict[str, Any]] = []
        state: dict[str, Any] = {
            "question": question,
            "search_candidate_ids": set(),
            "deep_read_ids": set(),
            "sources": [],
            "tool_counts": {},
            "remedial_attempts": 0,
            "remedial_used": False,
            "previous_candidate_ids": set(),
            "previous_deep_read_ids": set(),
            "agent_event_run_id": run_id,
            "chat_mode": policy.mode,
            "grep_first_performed": False,
            "grep_first_guard_used": False,
        }
        state["grep_first_required"] = self._requires_grep_first(question, policy)
        preloaded_hits: list[dict[str, Any]] = []
        preloaded_context = ""
        answer_guidance = ""
        if policy.preload_retrieval:
            preloaded_hits = self._preload_retrieval(question, scope)
            state["sources"] = self.rag_service.extract_sources(preloaded_hits) if hasattr(self.rag_service, "extract_sources") else []
            state["deep_read_ids"] = set(self._source_chunk_ids_from_hits(preloaded_hits))
            state["preloaded_hit_count"] = len(preloaded_hits)
            state["preloaded_source_count"] = len(state["sources"])
            preloaded_context = self._build_retrieved_context(preloaded_hits)
            answer_guidance = self._build_answer_guidance(question, preloaded_context)
        context = RuntimeToolContext(
            question=question,
            scope=scope,
            rag_service=self.rag_service,
            graph_retriever=self.graph_retriever,
            skills_manager=self.skills_manager,
            state=state,
        )
        messages = self._build_messages(
            question,
            scope,
            conversation_context,
            memory_context,
            attachments,
            policy=policy,
            contexts=preloaded_context,
            answer_guidance=answer_guidance,
        )
        tools = self.tool_registry.function_definitions(self._allowed_registered_tools(policy))
        root_span = self.span_repository.start_span(
            run_id=run_id,
            name="agent.execute",
            kind="root",
            input={"question_len": len(question), "tool_count": len(tools)},
            metadata={"trace_id": get_trace_id(), "knowledge_base_scope": scope.to_dict()},
        )
        obs_root = get_observability_sink().start_span(
            name="agent.execute",
            input={"question": question, "tool_count": len(tools)},
            metadata={"trace_id": get_trace_id(), "knowledge_base_scope": scope.to_dict()},
        )

        yield event_bus.emit(agent_event(
            "agent_query",
            run_id=run_id,
            sequence=event_sequence.next(),
            status="running",
            payload={
                "summary": "Received user question.",
                "question": truncate_text(question, 500),
                "chat_mode": policy.mode,
                "knowledge_base_scope": scope.to_dict(),
                "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
            },
        ))
        if policy.emit_initial_thought:
            yield event_bus.emit(agent_event(
                "agent_thought",
                run_id=run_id,
                sequence=event_sequence.next(),
                status="running",
                payload={
                    "phase": "initial_scan",
                    "summary": "Understanding the question and preparing knowledge-base retrieval.",
                    "completion_status": "running",
                    "metadata": {"tool_count": len(tools), "trace_id": get_trace_id(), "policy": policy.mode},
                },
            ))

        start_event = self._record_trace(
            trace,
            "AgentRuntimeStart",
            "running",
            "开始智能推理，准备检索知识库证据。",
            metadata={"tool_count": len(tools), "knowledge_base_scope": scope.to_dict(), "trace_id": get_trace_id(), "policy": policy.mode},
        )
        yield start_event

        empty_retries = 0
        repeated_responses = 0
        last_content = ""
        final_answer = ""
        final_status = "partial"
        try:
            if policy.quick and policy.preload_retrieval and not preloaded_hits:
                final_answer = self._fallback_answer_from_state(state)
                final_status = "partial"
            for round_number in range(1, policy.max_iterations + 1):
                if final_answer:
                    break
                round_start = time.time()
                round_span = self.span_repository.start_span(
                    run_id=run_id,
                    name=f"agent.round.{round_number}",
                    kind="round",
                    parent_span_id=root_span.span_id if root_span is not None else "",
                    input={"round": round_number, "message_count": len(messages)},
                    metadata={"trace_id": get_trace_id()},
                )
                obs_round = get_observability_sink().start_span(
                    name=f"agent.round.{round_number}",
                    input={"round": round_number, "message_count": len(messages), "max_iterations": policy.max_iterations},
                    metadata={"trace_id": get_trace_id(), "round": round_number, "policy": policy.mode},
                )
                yield self._record_trace(
                    trace,
                    "AgentRound",
                    "running",
                    f"第 {round_number} 轮：分析问题并选择下一步工具。",
                    metadata={"round": round_number, "trace_id": get_trace_id()},
                )
                response_message = self.run_react_iteration(
                    policy=policy,
                    messages=messages,
                    tools=tools,
                    state=state,
                    round_number=round_number,
                )
                content = str(response_message.get("content") or "").strip()
                tool_calls = list(response_message.get("tool_calls") or [])

                if content and content == last_content:
                    repeated_responses += 1
                else:
                    repeated_responses = 0
                last_content = content

                if not tool_calls:
                    if content and self._should_block_for_grep_first(state, policy):
                        self._append_grep_first_guard_message(messages, question)
                        yield self._record_trace(
                            trace,
                            "RequireGrepFirst",
                            "running",
                            "Knowledge-base retrieval requires exact term anchoring before semantic search or final answer.",
                            metadata={
                                "round": round_number,
                                "trace_id": get_trace_id(),
                                "policy": policy.mode,
                                "grep_first_required": True,
                            },
                        )
                        state["grep_first_guard_used"] = True
                        self.span_repository.finish_span(round_span, status="partial", output={"guard": "grep_first_required"})
                        obs_round.finish(output={"guard": "grep_first_required", "status": "partial"})
                        continue
                    if content and self._final_allowed(state, policy):
                        if self._has_unresolved_reflection_gap(state):
                            final_answer = self._fallback_answer_from_state(state)
                            final_status = "partial"
                            self.span_repository.finish_span(round_span, status="partial", output={"final": False, "reason": "unresolved_reflection_gap"})
                            obs_round.finish(output={"final": False, "reason": "unresolved_reflection_gap", "status": "partial"})
                        else:
                            final_answer = content
                            final_status = "completed"
                            self.span_repository.finish_span(round_span, status="completed", output={"final": True, "content_len": len(content)})
                            obs_round.finish(output={"final": True, "content_len": len(content), "status": "completed"})
                        break
                    if content and not self._final_allowed(state, policy):
                        messages.append(
                            {
                                "role": "user",
                                "content": "Runtime guard: search returned candidate evidence. Deep-read the relevant chunks with list_knowledge_chunks or get_document_info before final answer.",
                            }
                        )
                        yield self._record_trace(
                            trace,
                            "RequireDeepRead",
                            "running",
                            "已找到候选证据，继续深度读取后再回答。",
                            metadata={"round": round_number, "trace_id": get_trace_id()},
                        )
                        self.span_repository.finish_span(round_span, status="partial", output={"guard": "deep_read_required"})
                        obs_round.finish(output={"guard": "deep_read_required", "status": "partial"})
                        continue
                    empty_retries += 1
                    if empty_retries > policy.max_empty_retries:
                        final_answer = "无法从当前知识库证据中确定答案。"
                        self.span_repository.finish_span(round_span, status="failed", output={"empty_retries": empty_retries})
                        obs_round.finish(output={"empty_retries": empty_retries, "status": "failed"})
                        break
                    messages.append({"role": "user", "content": "Please continue by using an available tool or provide a final answer."})
                    self.span_repository.finish_span(round_span, status="partial", output={"empty_retry": empty_retries})
                    obs_round.finish(output={"empty_retry": empty_retries, "status": "partial"})
                    continue

                if self._should_block_tool_calls_for_grep_first(tool_calls, state, policy):
                    self._append_grep_first_guard_message(messages, question)
                    yield self._record_trace(
                        trace,
                        "RequireGrepFirst",
                        "running",
                        "Knowledge-base retrieval requires exact term anchoring before semantic expansion.",
                        metadata={
                            "round": round_number,
                            "trace_id": get_trace_id(),
                            "policy": policy.mode,
                            "grep_first_required": True,
                        },
                    )
                    state["grep_first_guard_used"] = True
                    self.span_repository.finish_span(round_span, status="partial", output={"guard": "grep_first_required"})
                    obs_round.finish(output={"guard": "grep_first_required", "status": "partial"})
                    continue

                empty_retries = 0
                assistant_message = {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": [_tool_call_message(call) for call in tool_calls],
                }
                messages.append(assistant_message)

                for index, call in enumerate(tool_calls, start=1):
                    function = call.get("function") or {}
                    tool_name = str(function.get("name") or "")
                    arguments = function.get("arguments") or "{}"
                    call_id = str(call.get("id") or f"round-{round_number}-tool-{index}")
                    call_payload = {
                        "call_id": call_id,
                        "tool": tool_name,
                        "action": "execute",
                        "input_summary": _input_summary(tool_name, arguments),
                        "metadata": {"round": round_number, "trace_id": get_trace_id(), "policy": policy.mode},
                    }
                    tool_events.append(call_payload)
                    yield event_bus.emit(tool_call_to_agent_event(call_payload, run_id=run_id, sequence=event_sequence.next()))
                    yield AgentRuntimeEvent("tool_call", call_payload)

                    if not self._policy_allows_tool(policy, tool_name):
                        observation_payload = {
                            "call_id": call_id,
                            "tool": tool_name,
                            "action": "execute",
                            "status": "failed",
                            "output_summary": f"tool not allowed by active policy: {tool_name}",
                            "source_chunk_ids": [],
                            "metadata": {
                                "round": round_number,
                                "call_id": call_id,
                                "policy": policy.mode,
                                "status": "unavailable",
                                "trace_id": get_trace_id(),
                            },
                        }
                        tool_events.append(observation_payload)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": tool_name,
                                "content": observation_payload["output_summary"],
                            }
                        )
                        yield event_bus.emit(tool_result_to_agent_event(observation_payload, run_id=run_id, sequence=event_sequence.next()))
                        yield AgentRuntimeEvent("tool_observation", observation_payload)
                        continue

                    tool_span = self.span_repository.start_span(
                        run_id=run_id,
                        name=f"tool.{tool_name}",
                        kind="tool",
                        parent_span_id=round_span.span_id if round_span is not None else "",
                        input={"tool": tool_name, "input_summary": call_payload["input_summary"]},
                        metadata={"round": round_number, "call_id": call_id, "trace_id": get_trace_id()},
                    )
                    obs_tool = get_observability_sink().start_span(
                        name=f"agent.tool.{tool_name}",
                        input={"tool": tool_name, "input_summary": call_payload["input_summary"], "call_id": call_id},
                        metadata={"round": round_number, "call_id": call_id, "trace_id": get_trace_id()},
                    )
                    obs_tool_context = activate_observation(obs_tool)
                    obs_tool_context.__enter__()
                    try:
                        result = self.tool_registry.execute(tool_name, arguments, context)
                    finally:
                        obs_tool_context.__exit__(None, None, None)
                    self.span_repository.finish_span(
                        tool_span,
                        status="completed" if result.success else "failed",
                        output={
                            "observation": result.observation,
                            "source_chunk_ids": result.source_chunk_ids,
                            "metadata": result.metadata,
                        },
                        error_message=result.error,
                    )
                    obs_tool.finish(
                        output={
                            "success": result.success,
                            "observation": result.observation,
                            "source_chunk_ids": result.source_chunk_ids,
                            "metadata": result.metadata,
                        },
                        error=RuntimeError(result.error) if result.error else None,
                    )
                    self._record_tool_state(tool_name, result, state)
                    observation = result.to_observation_text()
                    messages.append({"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": observation})
                    observation_payload = {
                        "call_id": call_id,
                        "tool": tool_name,
                        "action": "execute",
                        "status": "completed" if result.success else "failed",
                        "output_summary": result.observation or truncate_text(observation, 240),
                        "source_chunk_ids": result.source_chunk_ids,
                        "metadata": {
                            **result.metadata,
                            "round": round_number,
                            "call_id": call_id,
                            "source_titles": result.source_titles,
                            "trace_id": get_trace_id(),
                        },
                    }
                    tool_events.append(observation_payload)
                    if tool_name == "thinking":
                        yield event_bus.emit(self._thought_event_from_tool_result(result, state, run_id, event_sequence.next()))
                    yield event_bus.emit(tool_result_to_agent_event(observation_payload, run_id=run_id, sequence=event_sequence.next()))
                    yield AgentRuntimeEvent("tool_observation", observation_payload)
                    if tool_name == "thinking" and self._should_run_remedial_retrieval(state, policy):
                        yield from self._run_remedial_retrieval(
                            context=context,
                            state=state,
                            trace=trace,
                            tool_events=tool_events,
                            run_id=run_id,
                            event_sequence=event_sequence,
                            event_bus=event_bus,
                            round_number=round_number,
                        )

                yield self._record_trace(
                    trace,
                    "AgentRound",
                    "completed",
                    f"第 {round_number} 轮完成，调用 {len(tool_calls)} 次工具。",
                    metadata={
                        "round": round_number,
                        "tool_calls": len(tool_calls),
                        "duration_ms": int((time.time() - round_start) * 1000),
                        "trace_id": get_trace_id(),
                    },
                )
                self.span_repository.finish_span(
                    round_span,
                    status="completed",
                    output={"tool_calls": len(tool_calls), "duration_ms": int((time.time() - round_start) * 1000)},
                )
                obs_round.finish(
                    output={
                        "tool_calls": len(tool_calls),
                        "duration_ms": int((time.time() - round_start) * 1000),
                        "status": "completed",
                    }
                )
                if repeated_responses > policy.max_repeated_responses:
                    final_answer = "无法从当前知识库证据中确定答案。"
                    break
            else:
                final_answer = self._fallback_answer_from_state(state)

            sources = self._sources_from_state(state)
            reflection_status = "completed" if final_status == "completed" else "partial"
            yield event_bus.emit(self._reflection_event_from_state(
                state,
                run_id=run_id,
                sequence=event_sequence.next(),
                status=reflection_status,
                final_status=final_status,
            ))
            yield event_bus.emit(
                agent_event(
                    "agent_references",
                    run_id=run_id,
                    sequence=event_sequence.next(),
                    status="completed" if sources else "partial",
                    payload={
                        "items": sources,
                        "source_chunk_ids": list(state.get("deep_read_ids") or []),
                        "summary": f"Prepared {len(sources)} referenced source(s)." if sources else "No traceable references were available.",
                        "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
                    },
                )
            )
            yield AgentRuntimeEvent("sources", {"items": sources})
            yield AgentRuntimeEvent(
                "evidence_summary",
                {
                    "sufficient": final_status == "completed",
                    "sufficiency_reason": "已完成深度读取并生成回答。" if final_status == "completed" else "达到运行边界或证据不足。",
                    "tool_counts": dict(state.get("tool_counts") or {}),
                    "used_chunks": len(state.get("deep_read_ids") or []),
                    "source_chunk_ids": list(state.get("deep_read_ids") or []),
                },
            )
            yield event_bus.emit(
                agent_event(
                    "agent_final_answer",
                    run_id=run_id,
                    sequence=event_sequence.next(),
                    status="completed" if final_status == "completed" else "partial",
                    payload={
                        "answer": final_answer,
                        "answer_length": len(final_answer),
                        "citation_count": len(sources),
                        "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
                    },
                )
            )
            yield AgentRuntimeEvent("token", {"token": final_answer})
            final_payload = {
                "answer": final_answer,
                "citations": sources,
                "used_chunks": list(state.get("deep_read_ids") or []),
                "agent_trace": trace,
                "tool_calls": tool_events,
                "confidence": 0.7 if final_status == "completed" else 0.3,
            }
            yield self._record_trace(
                trace,
                "ReturnAnswer",
                "completed" if final_status == "completed" else "partial",
                "智能推理已完成。",
                metadata={
                    "rounds": min(policy.max_iterations, len([item for item in tool_events if item.get("call_id")]) or (1 if final_answer else 0)),
                    "tool_calls": len([item for item in tool_events if item.get("tool")]),
                    "duration_ms": int((time.time() - run_started) * 1000),
                    "remedial_used": bool(state.get("remedial_used")),
                    "trace_id": get_trace_id(),
                },
            )
            self.span_repository.finish_span(
                root_span,
                status="completed" if final_status == "completed" else "partial",
                output={"answer_len": len(final_answer), "tool_counts": dict(state.get("tool_counts") or {})},
            )
            obs_root.finish(
                output={
                    "answer_len": len(final_answer),
                    "tool_counts": dict(state.get("tool_counts") or {}),
                    "status": final_status,
                }
            )
            yield event_bus.emit(
                agent_event(
                    "agent_complete",
                    run_id=run_id,
                    sequence=event_sequence.next(),
                    status="completed" if final_status == "completed" else "partial",
                    payload={
                        "summary": "Agent run completed." if final_status == "completed" else "Agent run completed with insufficient evidence.",
                        "duration_ms": int((time.time() - run_started) * 1000),
                        "tool_counts": dict(state.get("tool_counts") or {}),
                        "source_count": len(sources),
                        "remedial_used": bool(state.get("remedial_used")),
                        "chat_mode": policy.mode,
                        "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
                    },
                )
            )
            yield AgentRuntimeEvent("final", final_payload)
        except Exception as exc:
            self.span_repository.finish_span(root_span, status="failed", error_message=str(exc))
            obs_root.finish(error=exc)
            yield event_bus.emit(
                agent_event(
                    "agent_error",
                    run_id=run_id,
                    sequence=event_sequence.next(),
                    status="failed",
                    payload={
                        "summary": truncate_text(str(exc), 240),
                        "chat_mode": policy.mode,
                        "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
                    },
                )
            )
            yield event_bus.emit(
                agent_event(
                    "agent_complete",
                    run_id=run_id,
                    sequence=event_sequence.next(),
                    status="failed",
                    payload={
                        "summary": "Agent run failed.",
                        "duration_ms": int((time.time() - run_started) * 1000),
                        "tool_counts": dict(state.get("tool_counts") or {}),
                        "chat_mode": policy.mode,
                        "metadata": {"trace_id": get_trace_id(), "policy": policy.mode},
                    },
                )
            )
            raise
        finally:
            event_bus.close()
            self.tool_registry.cleanup()

    def _thought_event_from_tool_result(
        self,
        result: RuntimeToolResult,
        state: dict[str, Any],
        run_id: str,
        sequence: int,
    ) -> AgentRuntimeEvent:
        metadata = dict(result.metadata or {})
        return agent_event(
            "agent_thought",
            run_id=run_id,
            sequence=sequence,
            status="partial" if metadata.get("gap") else "completed",
            payload={
                "phase": metadata.get("phase") or "reflection",
                "summary": metadata.get("summary") or result.observation or "Recorded public reasoning status.",
                "validity": metadata.get("validity") or "",
                "gap": metadata.get("gap") or "",
                "correction_query": metadata.get("correction_query") or "",
                "completion_status": metadata.get("completion_status") or state.get("reflection_completion_status") or "",
                "source_chunk_ids": metadata.get("source_chunk_ids") or result.source_chunk_ids,
                "metadata": {"trace_id": get_trace_id()},
            },
        )

    def run_react_iteration(
        self,
        *,
        policy: ChatRuntimePolicy,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        state: dict[str, Any],
        round_number: int,
    ) -> dict[str, Any]:
        response = self._call_model(messages, tools, tool_choice=policy.tool_choice)
        state["_last_react_phase"] = {
            "round": round_number,
            "policy": policy.mode,
            "tool_calls": len(response.get("tool_calls") or []),
            "has_content": bool(str(response.get("content") or "").strip()),
        }
        return response

    def _allowed_registered_tools(self, policy: ChatRuntimePolicy) -> tuple[str, ...]:
        registered = set(self.tool_registry.list_tools())
        return tuple(name for name in policy.enabled_tools if name in registered)

    def _policy_allows_tool(self, policy: ChatRuntimePolicy, tool_name: str) -> bool:
        return tool_name in set(self._allowed_registered_tools(policy))

    def _preload_retrieval(self, question: str, scope: KnowledgeBaseScope) -> list[dict[str, Any]]:
        hits = self.rag_service.recall_parent_hits(self.rag_service.hybrid_retrieve_hits(question, scope=scope), scope=scope)
        constraint_filter = getattr(self.rag_service, "filter_hits_for_question_constraints", None)
        if callable(constraint_filter):
            hits = constraint_filter(question, hits)
        return list(hits or [])

    def _build_retrieved_context(self, hits: list[dict[str, Any]]) -> str:
        builder = getattr(self.rag_service, "_build_context", None)
        if callable(builder):
            return str(builder(hits) or "")
        parts = []
        for index, hit in enumerate(hits[:8], start=1):
            metadata = hit.get("metadata", {}) if isinstance(hit, dict) else {}
            source = metadata.get("source") or f"source-{index}"
            content = str(hit.get("content") or "").strip() if isinstance(hit, dict) else ""
            if content:
                parts.append(f"[{index}] {source}\n{content}")
        return "\n\n".join(parts)

    def _build_answer_guidance(self, question: str, context: str) -> str:
        builder = getattr(self.rag_service, "_build_answer_style_guidance", None)
        if callable(builder):
            return str(builder(question, context) or "")
        return (
            "- Answer in concise, structured Markdown.\n"
            "- Use only the provided evidence.\n"
            "- If evidence is insufficient, say the knowledge base does not contain enough information."
        )

    def _source_chunk_ids_from_hits(self, hits: list[dict[str, Any]]) -> list[str]:
        chunk_ids: list[str] = []
        for hit in hits:
            metadata = hit.get("metadata", {}) if isinstance(hit, dict) else {}
            for key in ("chunk_id", "child_id", "parent_id"):
                value = str(metadata.get(key) or "").strip()
                if value:
                    chunk_ids.append(value)
                    break
            matched = metadata.get("matched_child_ids")
            if isinstance(matched, list):
                chunk_ids.extend(str(item) for item in matched if item)
        return list(dict.fromkeys(chunk_ids))

    def _reflection_event_from_state(
        self,
        state: dict[str, Any],
        *,
        run_id: str,
        sequence: int,
        status: str,
        final_status: str,
    ) -> AgentRuntimeEvent:
        gap = str(state.get("reflection_gap") or "").strip()
        correction_query = str(state.get("correction_query") or "").strip()
        sufficient = final_status == "completed" and not gap
        summary = (
            "Evidence has been deep-read and is sufficient for a sourced answer."
            if sufficient
            else gap or "Evidence remained insufficient for a certain answer."
        )
        return agent_event(
            "agent_reflection",
            run_id=run_id,
            sequence=sequence,
            status=status,
            payload={
                "phase": "final_check",
                "summary": summary,
                "validity": "sufficient" if sufficient else "insufficient_or_partial",
                "gap": "" if sufficient else gap,
                "correction_query": correction_query,
                "completion_status": "sufficient" if sufficient else "insufficient",
                "source_chunk_ids": list(state.get("deep_read_ids") or []),
                "metadata": {
                    "trace_id": get_trace_id(),
                    "remedial_attempts": int(state.get("remedial_attempts") or 0),
                    "remedial_used": bool(state.get("remedial_used")),
                },
            },
        )

    def _should_run_remedial_retrieval(self, state: dict[str, Any], policy: ChatRuntimePolicy) -> bool:
        if not policy.remedial_retrieval_enabled:
            return False
        if not str(state.get("reflection_gap") or "").strip():
            return False
        if not str(state.get("correction_query") or "").strip():
            return False
        if int(state.get("remedial_attempts") or 0) >= int(policy.max_remedial_retrieval_attempts):
            return False
        return self.tool_registry.get("knowledge_search") is not None

    def _has_unresolved_reflection_gap(self, state: dict[str, Any]) -> bool:
        if not str(state.get("reflection_gap") or "").strip():
            return False
        completion_status = str(state.get("reflection_completion_status") or "").strip().lower()
        return completion_status not in {"sufficient", "complete", "completed"}

    def _run_remedial_retrieval(
        self,
        *,
        context: RuntimeToolContext,
        state: dict[str, Any],
        trace: list[dict[str, Any]],
        tool_events: list[dict[str, Any]],
        run_id: str,
        event_sequence: AgentEventSequencer,
        event_bus: AgentEventBus,
        round_number: int,
    ) -> Generator[AgentRuntimeEvent, None, None]:
        correction_query = str(state.get("correction_query") or "").strip()
        if not correction_query:
            return
        attempt = int(state.get("remedial_attempts") or 0) + 1
        state["remedial_attempts"] = attempt
        state["remedial_used"] = True
        before_candidates = set(state.get("search_candidate_ids") or set())
        before_deep_reads = set(state.get("deep_read_ids") or set())
        yield event_bus.emit(
            agent_event(
                "agent_remedial_search",
                run_id=run_id,
                sequence=event_sequence.next(),
                status="running",
                payload={
                    "summary": "Running a follow-up knowledge-base search to repair an evidence gap.",
                    "gap": state.get("reflection_gap") or "",
                    "correction_query": correction_query,
                    "attempt": attempt,
                    "metadata": {"round": round_number, "trace_id": get_trace_id()},
                },
            )
        )
        search_result = yield from self._execute_controller_tool(
            tool_name="knowledge_search",
            arguments={"query": correction_query, "top_k": 8},
            context=context,
            state=state,
            trace=trace,
            tool_events=tool_events,
            run_id=run_id,
            event_sequence=event_sequence,
            event_bus=event_bus,
            round_number=round_number,
            call_id=f"remedial-{attempt}-search",
        )
        candidate_ids = [
            item
            for item in (search_result.candidate_ids or search_result.source_chunk_ids)
            if item and item not in before_candidates and item not in before_deep_reads
        ]
        candidate_ids = list(dict.fromkeys(candidate_ids))[:8]
        if not candidate_ids or self.tool_registry.get("list_knowledge_chunks") is None:
            state["reflection_completion_status"] = "insufficient"
            return
        read_result = yield from self._execute_controller_tool(
            tool_name="list_knowledge_chunks",
            arguments={"chunk_ids": candidate_ids, "knowledge_ids": candidate_ids, "limit": 8},
            context=context,
            state=state,
            trace=trace,
            tool_events=tool_events,
            run_id=run_id,
            event_sequence=event_sequence,
            event_bus=event_bus,
            round_number=round_number,
            call_id=f"remedial-{attempt}-read",
        )
        new_reads = [item for item in read_result.source_chunk_ids if item not in before_deep_reads]
        state["last_remedial_new_chunk_ids"] = new_reads
        if new_reads:
            state.pop("reflection_gap", None)
            state.pop("correction_query", None)
            state["reflection_completion_status"] = "sufficient"

    def _execute_controller_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        context: RuntimeToolContext,
        state: dict[str, Any],
        trace: list[dict[str, Any]],
        tool_events: list[dict[str, Any]],
        run_id: str,
        event_sequence: AgentEventSequencer,
        event_bus: AgentEventBus,
        round_number: int,
        call_id: str,
    ) -> Generator[AgentRuntimeEvent, None, RuntimeToolResult]:
        input_summary = _input_summary(tool_name, arguments)
        call_payload = {
            "call_id": call_id,
            "tool": tool_name,
            "action": "execute",
            "input_summary": input_summary,
            "metadata": {"round": round_number, "controller": "remedial_retrieval", "trace_id": get_trace_id()},
        }
        tool_events.append(call_payload)
        yield event_bus.emit(tool_call_to_agent_event(call_payload, run_id=run_id, sequence=event_sequence.next()))
        yield AgentRuntimeEvent("tool_call", call_payload)
        result = self.tool_registry.execute(tool_name, arguments, context)
        self._record_tool_state(tool_name, result, state)
        observation = result.to_observation_text()
        observation_payload = {
            "call_id": call_id,
            "tool": tool_name,
            "action": "execute",
            "status": "completed" if result.success else "failed",
            "output_summary": result.observation or truncate_text(observation, 240),
            "source_chunk_ids": result.source_chunk_ids,
            "metadata": {
                **result.metadata,
                "round": round_number,
                "call_id": call_id,
                "source_titles": result.source_titles,
                "controller": "remedial_retrieval",
                "trace_id": get_trace_id(),
            },
        }
        tool_events.append(observation_payload)
        yield event_bus.emit(tool_result_to_agent_event(observation_payload, run_id=run_id, sequence=event_sequence.next()))
        yield AgentRuntimeEvent("tool_observation", observation_payload)
        return result

    def _build_messages(
        self,
        question: str,
        scope: KnowledgeBaseScope,
        conversation_context: str | dict[str, Any] | None,
        memory_context: str | None,
        attachments: list[dict[str, Any]] | None,
        *,
        policy: ChatRuntimePolicy | None = None,
        contexts: list[dict[str, Any]] | str | None = None,
        answer_guidance: str = "",
    ) -> list[dict[str, Any]]:
        policy = policy or resolve_chat_runtime_policy("reasoning", self.config)
        system_prompt = self.prompt_catalog.render(
            policy.prompt_template_id,
            language="zh-CN",
            web_search_enabled=self.config.web_search_enabled,
            knowledge_bases=scope_to_prompt_kbs(scope, getattr(self.rag_service, "knowledge_base_service", None)),
            tools=[item for item in self.tool_registry.metadata() if item.get("name") in set(self._allowed_registered_tools(policy))],
            skills=self.skills_manager.metadata() if self.skills_manager is not None else [],
        )
        knowledge_bases = scope_to_prompt_kbs(scope, getattr(self.rag_service, "knowledge_base_service", None))
        user_content = self.context_catalog.render(
            policy.context_template_id,
            query=question,
            language="zh-CN",
            contexts=contexts,
            conversation_context=conversation_context,
            memory_context=memory_context,
            temporary_attachments=attachments or [],
            knowledge_base_scope=scope.to_dict(),
            knowledge_bases=knowledge_bases,
            answer_guidance=answer_guidance,
        )
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]

    def _call_model(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, tool_choice: str = "auto") -> dict[str, Any]:
        kwargs = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools and tool_choice != "none":
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        generation = get_observability_sink().start_generation(
            name="chat.completion",
            model=self.chat_model,
            input={"messages": messages, "tool_count": len(tools)},
            metadata={"has_tools": bool(tools), "trace_id": get_trace_id()},
            model_parameters={"temperature": 0.2, "tool_choice": kwargs.get("tool_choice", "")},
        )
        try:
            response = self.llm_client.chat.completions.create(**kwargs)
        except Exception as exc:
            generation.finish(error=exc)
            raise
        message = response.choices[0].message
        if hasattr(message, "model_dump"):
            data = message.model_dump()
        elif isinstance(message, dict):
            data = dict(message)
        else:
            data = {
                "content": getattr(message, "content", ""),
                "tool_calls": getattr(message, "tool_calls", None),
            }
        data["tool_calls"] = [_normalize_tool_call(call) for call in (data.get("tool_calls") or [])]
        usage = getattr(response, "usage", None)
        generation.finish(
            output={"content": data.get("content") or "", "tool_calls": data["tool_calls"], "finish_reason": getattr(response.choices[0], "finish_reason", "")},
            usage=_token_usage(usage),
        )
        return data

    def _final_allowed(self, state: dict[str, Any], policy: ChatRuntimePolicy | None = None) -> bool:
        if policy is not None and not policy.require_deep_read:
            return True
        if policy is not None and policy.grep_first_enabled and state.get("grep_first_required") and not state.get("grep_first_performed"):
            return False
        candidates = set(state.get("search_candidate_ids") or set())
        if not candidates:
            return True
        return bool(set(state.get("deep_read_ids") or set()))

    def _record_tool_state(self, tool_name: str, result: RuntimeToolResult, state: dict[str, Any]) -> None:
        counts = state.setdefault("tool_counts", {})
        counts[tool_name] = int(counts.get(tool_name, 0)) + 1
        if tool_name == "grep_chunks" and result.success:
            state["grep_first_performed"] = True
        if tool_name == "knowledge_search" and result.success:
            state["semantic_search_performed"] = True
        if result.candidate_ids:
            state.setdefault("previous_candidate_ids", set()).update(state.get("search_candidate_ids") or set())
            state.setdefault("search_candidate_ids", set()).update(result.candidate_ids)
        if result.deep_read or tool_name in {"list_knowledge_chunks", "get_document_info"}:
            state.setdefault("previous_deep_read_ids", set()).update(state.get("deep_read_ids") or set())
            state.setdefault("deep_read_ids", set()).update(result.source_chunk_ids or result.candidate_ids)
        if result.source_titles:
            for title in result.source_titles:
                state.setdefault("sources", []).append({"source": title, "score": 0.0})

    def _requires_grep_first(self, question: str, policy: ChatRuntimePolicy) -> bool:
        if not policy.grep_first_enabled or policy.quick:
            return False
        allowed = set(self._allowed_registered_tools(policy))
        if "grep_chunks" not in allowed:
            return False
        q = question.strip().lower()
        if not q:
            return False
        conversational = {
            "hi",
            "hello",
            "hey",
            "thanks",
            "thank you",
            "bye",
            "你好",
            "您好",
            "谢谢",
            "再见",
        }
        if q in conversational:
            return False
        non_retrieval_markers = [
            "translate",
            "rewrite",
            "polish",
            "summarize this conversation",
            "翻译",
            "润色",
            "改写",
            "写一段",
            "生成一段",
        ]
        if any(marker in q for marker in non_retrieval_markers):
            return False
        factual_markers = [
            "what",
            "when",
            "where",
            "which",
            "who",
            "how",
            "why",
            "version",
            "config",
            "support",
            "dependency",
            "impact",
            "error",
            "什么时候",
            "什么",
            "哪个",
            "哪些",
            "哪里",
            "谁",
            "如何",
            "怎么",
            "为什么",
            "上线",
            "版本",
            "配置",
            "支持",
            "依赖",
            "影响",
            "故障",
            "报错",
        ]
        return any(marker in q for marker in factual_markers) or bool(re.search(r"[\u4e00-\u9fff]{3,}|[a-z0-9_]{3,}", q))

    def _should_block_for_grep_first(self, state: dict[str, Any], policy: ChatRuntimePolicy) -> bool:
        return bool(
            policy.grep_first_enabled
            and state.get("grep_first_required")
            and not state.get("grep_first_performed")
            and not state.get("grep_first_guard_used")
        )

    def _should_block_tool_calls_for_grep_first(
        self,
        tool_calls: list[dict[str, Any]],
        state: dict[str, Any],
        policy: ChatRuntimePolicy,
    ) -> bool:
        if not self._should_block_for_grep_first(state, policy):
            return False
        tool_names = [str((call.get("function") or {}).get("name") or "") for call in tool_calls]
        if "grep_chunks" in tool_names:
            return False
        retrieval_tools = {"knowledge_search", "query_knowledge_graph"}
        return any(name in retrieval_tools for name in tool_names)

    def _append_grep_first_guard_message(self, messages: list[dict[str, Any]], question: str) -> None:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Runtime guard: this knowledge-base question requires exact term anchoring before semantic search "
                    "or final answer. Call grep_chunks first. Use your language and domain knowledge to include "
                    "synonyms, aliases, abbreviations, English names, legacy names, product names, and time/action "
                    f"variants for this question: {question}"
                ),
            }
        )

    def _sources_from_state(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        sources = []
        seen = set()
        for item in state.get("sources", []):
            source = str(item.get("source") or "").strip()
            if source and source not in seen:
                sources.append(item)
                seen.add(source)
        return sources

    def _fallback_answer_from_state(self, state: dict[str, Any]) -> str:
        reason = (
            "evidence was retrieved but remained insufficient for a certain answer"
            if state.get("deep_read_ids")
            else "no sufficient knowledge-base evidence was found"
        )
        try:
            return PromptTemplateCatalog.load_directory("config/prompt_templates").render(
                "fallback_response",
                {"query": str(state.get("question") or ""), "reason": reason},
                mode="reasoning",
            )
        except PromptTemplateError as exc:
            logger.warning("Fallback prompt render failed, using built-in fallback: %s", exc)
        if state.get("deep_read_ids"):
            return "已检索并读取到部分证据，但当前推理轮次不足以形成确定答案。请缩小问题范围或重试。"
        return "无法从当前知识库证据中确定答案。"

    def _record_trace(
        self,
        trace: list[dict[str, Any]],
        stage: str,
        status: str,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRuntimeEvent:
        event = self._trace_event(stage, status, summary, metadata=metadata)
        trace.append(event.payload)
        return event

    def _trace_event(self, stage: str, status: str, summary: str, *, metadata: dict[str, Any] | None = None) -> AgentRuntimeEvent:
        logger.info(
            "agent_runtime.trace",
            extra={"stage": stage, "status": status, "trace_id": get_trace_id(), **(metadata or {})},
        )
        return AgentRuntimeEvent(
            "agent_trace",
            {
                "stage": stage,
                "status": status,
                "summary": summary,
                "metadata": scrub_private_fields(sanitize_payload(metadata or {}, limit=1024)),
            },
        )


def _normalize_tool_call(call: Any) -> dict[str, Any]:
    if hasattr(call, "model_dump"):
        data = call.model_dump()
    elif isinstance(call, dict):
        data = dict(call)
    else:
        function = getattr(call, "function", None)
        data = {
            "id": getattr(call, "id", ""),
            "type": getattr(call, "type", "function"),
            "function": {
                "name": getattr(function, "name", "") if function is not None else "",
                "arguments": getattr(function, "arguments", "{}") if function is not None else "{}",
            },
        }
    function = data.get("function") or {}
    if hasattr(function, "model_dump"):
        function = function.model_dump()
    data["function"] = dict(function)
    return data


def _tool_call_message(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(call.get("id") or ""),
        "type": "function",
        "function": {
            "name": str((call.get("function") or {}).get("name") or ""),
            "arguments": str((call.get("function") or {}).get("arguments") or "{}"),
        },
    }


def _input_summary(tool_name: str, arguments: Any) -> str:
    query = ""
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
        if isinstance(parsed.get("queries"), list):
            query = f"{len(parsed.get('queries') or [])} query variants"
        else:
            query = str(parsed.get("query") or parsed.get("skill_name") or "")
    except Exception:
        query = ""
    if query:
        return f"{tool_name}: {truncate_text(query, 120)}"
    return tool_name


def _token_usage(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    return {"input": prompt, "output": completion, "total": total, "unit": "TOKENS"} if total else {}
