# Unified Chat ReAct Runtime Validation

Change: `unify-chat-react-event-runtime`

## Expected Event Shapes

Quick unified runtime:

```text
conversation_id
  -> agent_query
  -> agent_references / sources
  -> agent_final_answer
  -> token
  -> agent_complete
  -> final metadata
  -> [DONE]
```

Reasoning runtime:

```text
conversation_id
  -> agent_query
  -> agent_thought
  -> agent_tool_call / tool_call
  -> agent_tool_result / tool_observation
  -> agent_reflection
  -> optional agent_remedial_search
  -> agent_references / sources
  -> agent_final_answer
  -> token
  -> agent_complete
  -> final metadata
  -> [DONE]
```

## Commands

```powershell
cd backend
.\.venv\Scripts\python.exe -m py_compile app\models\agent_runtime.py app\services\agent_runtime.py app\services\agent_runtime_tools.py app\main.py
.\.venv\Scripts\python.exe -m unittest tests.test_agent_runtime_loop tests.test_agentic_chat_stream -v
.\.venv\Scripts\python.exe -m unittest tests.test_runtime_config.RuntimeConfigTests.test_runtime_config_reads_unified_quick_runtime_policy_values -v

cd frontend
node --test .\app\lib\agent-stream.test.mjs
```

## Result

- Backend py_compile passed.
- Backend Agent runtime and chat stream tests passed.
- Focused unified quick runtime config test passed.
- Frontend agent stream tests passed.
- `node --test` still prints the existing `MODULE_TYPELESS_PACKAGE_JSON` warning; tests pass.

## Note

Running the full `tests.test_runtime_config` module in this local shell also picked up real host environment variables for Langfuse and Milvus BM25, causing unrelated default-value assertions to fail. The focused quick-runtime config test was run with explicit overrides and passed.
