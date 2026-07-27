## Why

The backend already has local processing span traces, but a local Langfuse instance cannot be plugged in cleanly with the user's current `LANGFUSE_BASE_URL="http://localhost:3001"` setting. Operators need one observable flow that shows document processing, retrieval, agent/tool activity, and failures in Langfuse without replacing the SQLite span tree or local log files.

## What Changes

- Add first-class Langfuse configuration that supports both `LANGFUSE_BASE_URL` and the existing `LANGFUSE_HOST` alias, validates public/secret keys, and reports clear startup/runtime diagnostics.
- Add the `langfuse` Python dependency or optional dependency handling so enabling Langfuse does not silently fail because the package is missing.
- Keep SQLite `knowledge_processing_spans`, local processing trace files, and request logs as source-of-truth local evidence; Langfuse is an external observability sink.
- Emit sanitized Langfuse traces/spans for document processing attempts, parsing, chunking, embedding/indexing, multimodal work, postprocess, retrieval phases, agent runtime iterations, and tool calls.
- Propagate request trace IDs, document IDs, knowledge-base scope, task IDs, span IDs, and safe metadata into Langfuse so UI/API/log/database traces can be correlated.
- Add a lightweight health/debug endpoint or startup log message that confirms whether Langfuse is enabled, configured, package-available, and connected.
- Update `.env.example`, README, and development docs with local Langfuse setup using `LANGFUSE_BASE_URL=http://localhost:3001`.

## Capabilities

### New Capabilities

- `langfuse-local-observability`: Covers local Langfuse configuration, client initialization, sanitized trace/span emission, correlation metadata, fallback behavior, and validation.

### Modified Capabilities

None.

## Impact

- Backend config loading and environment examples.
- `backend/app/services/processing_trace.py` and any shared observability service introduced for Langfuse client management.
- Document processing spans, retrieval debug instrumentation, agent runtime/tool trace emission, and request logging correlation.
- Backend dependency manifest.
- README and development troubleshooting docs.
