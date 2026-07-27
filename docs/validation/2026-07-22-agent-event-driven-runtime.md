# Agent Event Driven Runtime Validation

Change: `add-agent-event-driven-runtime`

Representative questions:

- `可适配万兆堆叠线缆的交换机`
- `某型号支持哪些认证方式？`
- `Redis version?` with an initial reflection gap and correction query

Expected reasoning-mode event order:

```text
agent_query
agent_thought
agent_tool_call / tool_call
agent_tool_result / tool_observation
agent_reflection
agent_remedial_search when a repairable gap exists
agent_references / sources
evidence_summary
agent_final_answer / token
agent_complete
final metadata
[DONE]
```

Validation commands:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_agent_runtime_loop tests.test_agentic_chat_stream -v

cd ..\frontend
node --test .\app\lib\agent-stream.test.mjs
npm run build
```

Acceptance notes:

- `agent_references` and compatible `sources` must arrive before the first answer `token`.
- Token-only clients must not append final answer text twice.
- Public thought/reflection events must scrub private reasoning fields.
- Remedial retrieval must be bounded and skipped in quick mode.

Observed results:

- Backend focused tests: 19 passed.
- Frontend agent stream tests: 10 passed.
- Frontend production build: passed.
