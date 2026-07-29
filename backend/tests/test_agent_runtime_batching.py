from __future__ import annotations

import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar

from app.models.agent_runtime import (
    AgentRuntimeConfig,
    RuntimeStateDelta,
    RuntimeToolResult,
    ToolExecutionClass,
    resolve_chat_runtime_policy,
)
from app.services.agent.agent_runtime_tools import RuntimeToolContext, ToolRegistry
from app.services.retrieval.rag_service import RAGService
from tests.test_agent_runtime_loop import (
    FakeClient,
    FakeMessage,
    FakeResponse,
    build_runtime,
)


class BatchingCompletions:
    def __init__(self):
        self.calls = 0
        self.kwargs = []

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        if self.calls == 1:
            return FakeResponse(
                FakeMessage(
                    tool_calls=[
                        {
                            "id": "grep-1",
                            "type": "function",
                            "function": {
                                "name": "grep_chunks",
                                "arguments": '{"query":"Redis|缓存|cache","top_k":2}',
                            },
                        },
                        {
                            "id": "semantic-1",
                            "type": "function",
                            "function": {
                                "name": "knowledge_search",
                                "arguments": '{"query":"Redis cache dependency","top_k":2}',
                            },
                        },
                    ]
                )
            )
        if self.calls == 2:
            return FakeResponse(
                FakeMessage(
                    tool_calls=[
                        {
                            "id": "read-1",
                            "type": "function",
                            "function": {
                                "name": "list_knowledge_chunks",
                                "arguments": '{"chunk_ids":["c1"],"limit":2}',
                            },
                        },
                        {
                            "id": "read-2",
                            "type": "function",
                            "function": {
                                "name": "list_knowledge_chunks",
                                "arguments": '{"knowledge_ids":["doc-1"],"limit":2}',
                            },
                        },
                    ]
                )
            )
        return FakeResponse(FakeMessage(content="Redis is used by API Gateway."))


class RepeatingCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return FakeResponse(
            FakeMessage(
                tool_calls=[
                    {
                        "id": f"grep-{self.calls}",
                        "type": "function",
                        "function": {
                            "name": "grep_chunks",
                            "arguments": '{"query":"Redis|cache"}',
                        },
                    }
                ]
            )
        )


class ProviderFallbackCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("parallel_tool_calls"):
            raise RuntimeError("unsupported parameter parallel_tool_calls")
        return FakeResponse(FakeMessage(content="Hello."))


class StreamCompletions:
    def __init__(self, chunks):
        self.chunks = chunks

    def create(self, **kwargs):
        return iter(self.chunks)


class SlowToolCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return FakeResponse(
            FakeMessage(
                tool_calls=[
                    {
                        "id": f"slow-{self.calls}",
                        "type": "function",
                        "function": {"name": "slow_tool", "arguments": "{}"},
                    }
                ]
            )
        )


class AliasRetryCompletions:
    def __init__(self):
        self.calls = 0
        self.kwargs = []

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        scripted = {
            1: [
                {
                    "id": "grep-initial",
                    "type": "function",
                    "function": {
                        "name": "grep_chunks",
                        "arguments": '{"query":"风控系统|风控平台|Risk.Control"}',
                    },
                }
            ],
            2: [
                {
                    "id": "read-initial",
                    "type": "function",
                    "function": {
                        "name": "list_knowledge_chunks",
                        "arguments": '{"chunk_ids":["c1"]}',
                    },
                }
            ],
            3: [
                {
                    "id": "grep-alias",
                    "type": "function",
                    "function": {
                        "name": "grep_chunks",
                        "arguments": '{"query":"智能风控中台|风控中台"}',
                    },
                }
            ],
        }
        if self.calls in scripted:
            return FakeResponse(FakeMessage(tool_calls=scripted[self.calls]))
        return FakeResponse(FakeMessage(content="The evidence-backed answer."))


class StreamedTerminalSynthesisCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse(
                FakeMessage(
                    tool_calls=[
                        {
                            "id": "grep",
                            "type": "function",
                            "function": {
                                "name": "grep_chunks",
                                "arguments": '{"query":"Redis|cache"}',
                            },
                        }
                    ]
                )
            )
        if self.calls == 2:
            return FakeResponse(
                FakeMessage(
                    tool_calls=[
                        {
                            "id": "read",
                            "type": "function",
                            "function": {
                                "name": "list_knowledge_chunks",
                                "arguments": '{"chunk_ids":["c1"]}',
                            },
                        }
                    ]
                )
            )
        self.stream_enabled = kwargs.get("stream") is True
        self.tools_disabled = not kwargs.get("tools")
        return iter(
            [
                {"choices": [{"delta": {"content": "Redis is "}}]},
                {
                    "choices": [
                        {
                            "delta": {"content": "used by API Gateway."},
                            "finish_reason": "stop",
                        }
                    ]
                },
            ]
        )


class DelayTool:
    description = "Controlled test tool."
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(
        self,
        name: str,
        delay: float,
        candidate_id: str,
        execution_class: ToolExecutionClass,
    ):
        self.name = name
        self.delay = delay
        self.candidate_id = candidate_id
        self.execution_class = execution_class

    def execute(self, arguments, context):
        time.sleep(self.delay)
        return RuntimeToolResult(
            success=True,
            output=self.candidate_id,
            observation=self.candidate_id,
            candidate_ids=[self.candidate_id],
            state_delta=RuntimeStateDelta(candidate_ids=[self.candidate_id]),
        )


class FailingTool(DelayTool):
    def execute(self, arguments, context):
        raise RuntimeError("independent lookup failed")


class AgentRuntimeBatchingTests(unittest.TestCase):
    def test_autonomous_three_turn_path_batches_search_and_deep_reads(self):
        completions = BatchingCompletions()
        runtime = build_runtime(
            completions=completions,
            enabled_tools=("grep_chunks", "knowledge_search", "list_knowledge_chunks"),
        )
        runtime.config.max_iterations = 2
        runtime.config.max_parallel_workers = 4

        events = list(
            runtime.stream_query_events(
                "What uses Redis?",
                scope=runtime.rag_service.default_scope,
            )
        )

        calls = [
            event.payload
            for event in events
            if event.event_type == "agent_tool_call"
        ]
        self.assertEqual(
            ["grep_chunks", "knowledge_search", "list_knowledge_chunks", "list_knowledge_chunks"],
            [call["tool"] for call in calls],
        )
        self.assertEqual(3, completions.calls)
        self.assertTrue(completions.kwargs[0]["parallel_tool_calls"])
        self.assertNotIn("agent_remedial_search", [event.event_type for event in events])
        self.assertEqual(
            "Redis is used by API Gateway.",
            [event for event in events if event.event_type == "final"][-1].payload["answer"],
        )
        third_messages = completions.kwargs[2]["messages"]
        tool_messages = [message for message in third_messages if message["role"] == "tool"]
        self.assertEqual(
            ["list_knowledge_chunks", "list_knowledge_chunks"],
            [message["name"] for message in tool_messages[-2:]],
        )

    def test_parallel_safe_calls_overlap_and_merge_in_declared_order(self):
        runtime = build_runtime(enabled_tools=())
        registry = ToolRegistry()
        registry.register(
            DelayTool("slow_first", 0.18, "c1", ToolExecutionClass.PARALLEL_SAFE)
        )
        registry.register(
            DelayTool("fast_second", 0.04, "c2", ToolExecutionClass.PARALLEL_SAFE)
        )
        runtime.tool_registry = registry
        runtime.config.enabled_tools = ("slow_first", "fast_second")
        runtime.config.max_parallel_workers = 2
        runtime.config.local_concurrency_enabled = True
        policy = resolve_chat_runtime_policy("reasoning", runtime.config)
        calls = [
            {
                "id": "slow",
                "function": {"name": "slow_first", "arguments": "{}"},
            },
            {
                "id": "fast",
                "function": {"name": "fast_second", "arguments": "{}"},
            },
        ]
        batch = runtime._build_action_batch(
            calls,
            round_number=1,
            policy=policy,
            remaining_tool_calls=4,
        )
        context = RuntimeToolContext(
            "q",
            runtime.rag_service.default_scope,
            runtime.rag_service,
            state={},
        )

        started = time.perf_counter()
        executions = runtime._execute_action_batch(
            batch,
            context=context,
            run_id="test",
            round_span=None,
            policy=policy,
        )
        elapsed = time.perf_counter() - started
        state = {"search_candidate_ids": [], "deep_read_ids": [], "sources": []}
        for execution in executions:
            runtime._record_tool_state(execution.call.tool_name, execution.result, state)

        self.assertLess(elapsed, 0.30)
        self.assertEqual(["slow_first", "fast_second"], [item.call.tool_name for item in executions])
        self.assertEqual(["c1", "c2"], state["search_candidate_ids"])
        self.assertEqual({}, context.state)

    def test_serial_barrier_prevents_overlap_across_segments(self):
        runtime = build_runtime(enabled_tools=())
        registry = ToolRegistry()
        registry.register(DelayTool("left", 0.08, "l", ToolExecutionClass.PARALLEL_SAFE))
        registry.register(DelayTool("barrier", 0.08, "s", ToolExecutionClass.SERIAL))
        registry.register(DelayTool("exclusive", 0.08, "x", ToolExecutionClass.EXCLUSIVE))
        registry.register(DelayTool("right", 0.08, "r", ToolExecutionClass.PARALLEL_SAFE))
        runtime.tool_registry = registry
        runtime.config.enabled_tools = ("left", "barrier", "exclusive", "right")
        runtime.config.max_parallel_workers = 3
        policy = resolve_chat_runtime_policy("reasoning", runtime.config)
        batch = runtime._build_action_batch(
            [
                {"id": "1", "function": {"name": "left", "arguments": "{}"}},
                {"id": "2", "function": {"name": "barrier", "arguments": "{}"}},
                {"id": "3", "function": {"name": "exclusive", "arguments": "{}"}},
                {"id": "4", "function": {"name": "right", "arguments": "{}"}},
            ],
            round_number=1,
            policy=policy,
            remaining_tool_calls=4,
        )
        context = RuntimeToolContext("q", runtime.rag_service.default_scope, runtime.rag_service)

        started = time.perf_counter()
        runtime._execute_action_batch(
            batch,
            context=context,
            run_id="test",
            round_span=None,
            policy=policy,
        )

        self.assertGreaterEqual(time.perf_counter() - started, 0.30)

    def test_serial_and_concurrent_schedulers_commit_equivalent_results(self):
        def execute(local_concurrency_enabled):
            runtime = build_runtime(enabled_tools=())
            registry = ToolRegistry()
            registry.register(
                DelayTool("first", 0.03, "c1", ToolExecutionClass.PARALLEL_SAFE)
            )
            registry.register(
                DelayTool("second", 0.01, "c2", ToolExecutionClass.PARALLEL_SAFE)
            )
            runtime.tool_registry = registry
            runtime.config.enabled_tools = ("first", "second")
            runtime.config.local_concurrency_enabled = local_concurrency_enabled
            policy = resolve_chat_runtime_policy("reasoning", runtime.config)
            batch = runtime._build_action_batch(
                [
                    {"id": "1", "function": {"name": "first", "arguments": "{}"}},
                    {"id": "2", "function": {"name": "second", "arguments": "{}"}},
                ],
                round_number=1,
                policy=policy,
                remaining_tool_calls=2,
            )
            executions = runtime._execute_action_batch(
                batch,
                context=RuntimeToolContext(
                    "q",
                    runtime.rag_service.default_scope,
                    runtime.rag_service,
                ),
                run_id="test",
                round_span=None,
                policy=policy,
            )
            state = {"search_candidate_ids": [], "deep_read_ids": [], "sources": []}
            for execution in executions:
                runtime._record_tool_state(
                    execution.call.tool_name,
                    execution.result,
                    state,
                )
            return (
                [execution.call.tool_name for execution in executions],
                [execution.result.output for execution in executions],
                state["search_candidate_ids"],
            )

        self.assertEqual(execute(False), execute(True))

    def test_independent_failure_does_not_cancel_other_parallel_safe_call(self):
        runtime = build_runtime(enabled_tools=())
        registry = ToolRegistry()
        registry.register(
            FailingTool("fails", 0.0, "bad", ToolExecutionClass.PARALLEL_SAFE)
        )
        registry.register(
            DelayTool("works", 0.01, "good", ToolExecutionClass.PARALLEL_SAFE)
        )
        runtime.tool_registry = registry
        runtime.config.enabled_tools = ("fails", "works")
        policy = resolve_chat_runtime_policy("reasoning", runtime.config)
        batch = runtime._build_action_batch(
            [
                {"id": "1", "function": {"name": "fails", "arguments": "{}"}},
                {"id": "2", "function": {"name": "works", "arguments": "{}"}},
            ],
            round_number=1,
            policy=policy,
            remaining_tool_calls=2,
        )

        executions = runtime._execute_action_batch(
            batch,
            context=RuntimeToolContext(
                "q",
                runtime.rag_service.default_scope,
                runtime.rag_service,
            ),
            run_id="test",
            round_span=None,
            policy=policy,
        )

        self.assertFalse(executions[0].result.success)
        self.assertEqual(
            "tool_execution_failed",
            executions[0].result.structured_error.code,
        )
        self.assertTrue(executions[1].result.success)
        self.assertEqual(
            [1, 2],
            [execution.call.index for execution in executions],
        )

    def test_repeated_tool_signature_stops_without_reexecuting(self):
        completions = RepeatingCompletions()
        runtime = build_runtime(
            completions=completions,
            enabled_tools=("grep_chunks",),
        )
        runtime.config.max_repeated_tool_batches = 1

        events = list(
            runtime.stream_query_events(
                "What uses Redis?",
                scope=runtime.rag_service.default_scope,
            )
        )

        calls = [
            event for event in events if event.event_type == "agent_tool_call"
        ]
        complete = [
            event.payload for event in events if event.event_type == "agent_complete"
        ][-1]
        self.assertEqual(2, len(calls))
        self.assertEqual(3, completions.calls)
        self.assertEqual("repeated_action_batch", complete["stop_reason"])

    def test_provider_parallel_option_falls_back_and_is_cached(self):
        completions = ProviderFallbackCompletions()
        runtime = build_runtime(
            completions=completions,
            enabled_tools=("grep_chunks",),
        )

        events = list(
            runtime.stream_query_events(
                "hello",
                scope=runtime.rag_service.default_scope,
            )
        )
        self.assertEqual(2, len(completions.calls))
        self.assertTrue(completions.calls[0]["parallel_tool_calls"])
        self.assertNotIn("parallel_tool_calls", completions.calls[1])
        complete = [
            event.payload for event in events if event.event_type == "agent_complete"
        ][-1]
        self.assertTrue(complete["metadata"]["provider_parallel_fallback"])

        list(
            runtime.stream_query_events(
                "hello again",
                scope=runtime.rag_service.default_scope,
            )
        )
        self.assertEqual(3, len(completions.calls))
        self.assertNotIn("parallel_tool_calls", completions.calls[2])

    def test_stream_parser_assembles_partial_tool_arguments(self):
        chunks = [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "function": {
                                        "name": "grep_",
                                        "arguments": '{"que',
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "name": "chunks",
                                        "arguments": 'ry":"Redis|cache"}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ]
        runtime = build_runtime(enabled_tools=("grep_chunks",))
        runtime.llm_client = FakeClient(StreamCompletions(chunks))

        response = runtime._call_model_stream_buffered(
            [{"role": "user", "content": "q"}],
            runtime.tool_registry.function_definitions(),
            parallel_tool_calls_mode="off",
        )

        self.assertEqual("grep_chunks", response["tool_calls"][0]["function"]["name"])
        self.assertEqual(
            '{"query":"Redis|cache"}',
            response["tool_calls"][0]["function"]["arguments"],
        )
        self.assertEqual("", response["content"])

    def test_partial_batch_budget_rejects_only_calls_beyond_remaining_capacity(self):
        runtime = build_runtime(enabled_tools=())
        registry = ToolRegistry()
        registry.register(
            DelayTool("first", 0.0, "c1", ToolExecutionClass.PARALLEL_SAFE)
        )
        registry.register(
            DelayTool("second", 0.0, "c2", ToolExecutionClass.PARALLEL_SAFE)
        )
        runtime.tool_registry = registry
        runtime.config.enabled_tools = ("first", "second")
        policy = resolve_chat_runtime_policy("reasoning", runtime.config)
        batch = runtime._build_action_batch(
            [
                {"id": "1", "function": {"name": "first", "arguments": "{}"}},
                {"id": "2", "function": {"name": "second", "arguments": "{}"}},
            ],
            round_number=1,
            policy=policy,
            remaining_tool_calls=1,
        )

        executions = runtime._execute_action_batch(
            batch,
            context=RuntimeToolContext(
                "q",
                runtime.rag_service.default_scope,
                runtime.rag_service,
            ),
            run_id="test",
            round_span=None,
            policy=policy,
        )

        self.assertTrue(executions[0].result.success)
        self.assertFalse(executions[1].result.success)
        self.assertEqual(
            "tool_call_budget_exceeded",
            executions[1].result.structured_error.code,
        )

    def test_wall_clock_budget_stops_before_another_model_round(self):
        completions = SlowToolCompletions()
        runtime = build_runtime(completions=completions, enabled_tools=())
        registry = ToolRegistry()
        registry.register(
            DelayTool("slow_tool", 1.05, "c1", ToolExecutionClass.SERIAL)
        )
        runtime.tool_registry = registry
        runtime.config.enabled_tools = ("slow_tool",)
        runtime.config.max_wall_clock_seconds = 1.0

        events = list(
            runtime.stream_query_events(
                "Run the slow lookup.",
                scope=runtime.rag_service.default_scope,
            )
        )

        complete = [
            event.payload for event in events if event.event_type == "agent_complete"
        ][-1]
        self.assertEqual(1, completions.calls)
        self.assertEqual("wall_clock_budget", complete["stop_reason"])
        self.assertEqual("partial", complete["status"])

    def test_request_scoped_retrieval_debug_isolated_across_threads(self):
        rag = object.__new__(RAGService)
        rag._retrieval_debug_context = ContextVar("test_retrieval_debug", default=None)
        rag._last_retrieval_debug_global = {}

        def run(label, delay):
            def operation():
                rag._last_retrieval_debug = {"query": label}
                time.sleep(delay)
                rag._last_retrieval_debug["finished"] = label
                return label

            return rag.run_with_retrieval_debug(operation)

        with ThreadPoolExecutor(max_workers=2) as executor:
            slow = executor.submit(run, "slow", 0.04)
            fast = executor.submit(run, "fast", 0.01)
            slow_result = slow.result()
            fast_result = fast.result()

        self.assertEqual(("slow", {"query": "slow", "finished": "slow"}), slow_result)
        self.assertEqual(("fast", {"query": "fast", "finished": "fast"}), fast_result)

    def test_normal_terminal_content_uses_safe_stream_chunks_when_enabled(self):
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {
                "choices": [
                    {
                        "delta": {"content": " world"},
                        "finish_reason": "stop",
                    }
                ]
            },
        ]
        runtime = build_runtime(enabled_tools=())
        runtime.llm_client = FakeClient(StreamCompletions(chunks))
        runtime.config.terminal_streaming_mode = "on"

        events = list(
            runtime.stream_query_events(
                "Say hello.",
                scope=runtime.rag_service.default_scope,
            )
        )

        tokens = [
            event.payload["token"] for event in events if event.event_type == "token"
        ]
        event_types = [event.event_type for event in events]
        self.assertEqual(["Hello", " world"], tokens)
        self.assertLess(event_types.index("sources"), event_types.index("token"))
        self.assertEqual("final", event_types[-1])

    def test_model_selects_new_alias_after_reading_initial_evidence(self):
        completions = AliasRetryCompletions()
        runtime = build_runtime(
            completions=completions,
            enabled_tools=("grep_chunks", "list_knowledge_chunks"),
        )

        events = list(
            runtime.stream_query_events(
                "风控系统什么时候上线？",
                scope=runtime.rag_service.default_scope,
            )
        )

        calls = [
            event.payload
            for event in events
            if event.event_type == "agent_tool_call"
        ]
        self.assertEqual(
            ["grep_chunks", "list_knowledge_chunks", "grep_chunks"],
            [call["tool"] for call in calls],
        )
        third_model_messages = completions.kwargs[2]["messages"]
        self.assertIn("Redis is used by API Gateway.", third_model_messages[-1]["content"])
        self.assertEqual("The evidence-backed answer.", events[-1].payload["answer"])
        self.assertNotIn("thinking", [call["tool"] for call in calls])

    def test_reserved_terminal_synthesis_streams_with_tools_disabled(self):
        completions = StreamedTerminalSynthesisCompletions()
        runtime = build_runtime(
            completions=completions,
            enabled_tools=("grep_chunks", "list_knowledge_chunks"),
        )
        runtime.config.max_iterations = 2
        runtime.config.terminal_streaming_mode = "auto"

        events = list(
            runtime.stream_query_events(
                "What uses Redis?",
                scope=runtime.rag_service.default_scope,
            )
        )

        tokens = [
            event.payload["token"] for event in events if event.event_type == "token"
        ]
        complete = [
            event.payload for event in events if event.event_type == "agent_complete"
        ][-1]
        self.assertTrue(completions.stream_enabled)
        self.assertTrue(completions.tools_disabled)
        self.assertEqual(["Redis is ", "used by API Gateway."], tokens)
        self.assertTrue(complete["terminal_synthesis_used"])


if __name__ == "__main__":
    unittest.main()
