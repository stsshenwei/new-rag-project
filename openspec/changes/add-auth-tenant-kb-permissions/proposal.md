## Why

The knowledge base now has Raw RAG, keyword retrieval, graph retrieval, agentic workflow, and evaluation, but all access still behaves like a single shared tenant. Enterprise usage needs a real permission boundary so users, API tokens, retrieval tools, and Agent workflows can only access authorized knowledge bases, documents, chunks, and graph evidence.

## What Changes

- Add an API-token based authentication foundation for backend APIs.
- Reuse the final workspace, knowledge base, ownership schema, clean-rebuild initialization, management API, and UI from `add-multi-knowledge-base-domain`; add tenant, team, membership, and role models for enterprise access control.
- Add a `PermissionScope` resolved from the current principal and requested filters.
- Intersect principal permissions with the existing `KnowledgeBaseScope`; do not recreate knowledge-base ownership columns or migrations.
- Enforce permission scope across document upload, ingest, listing, file/content access, deletion, Raw RAG, SQLite FTS5 keyword search, Milvus vector retrieval, GraphRetriever, `/rag/query`, and `/chat/stream`.
- Replace the current Agent FSM permission placeholder with a real `CheckPermissionScope` step.
- Preserve a local single-tenant compatibility mode for development and existing tests.
- Do not add a frontend login screen, OAuth, SSO, or full user-management UI in this change.

## Capabilities

### New Capabilities

- `auth-tenant-permissions`: API-token authentication, users, tenants, teams, memberships, roles, and permission scope resolution over the existing knowledge-base domain.
- `scoped-knowledge-retrieval`: Permission-aware document access, Raw RAG, keyword search, vector retrieval, graph retrieval, and Agent workflow execution.

### Modified Capabilities

- None.

## Impact

- Backend data models and repositories gain user, tenant, team, membership, API token, and permission-scope persistence.
- Document and chunk ownership remain owned by `add-multi-knowledge-base-domain`; this change only authorizes access to those existing identities.
- Existing workspace/KB filters in Milvus, SQLite FTS5, document repositories, KG, and citations consume the authorized `KnowledgeBaseScope`; this change does not add a second tenant ownership column to evidence rows.
- GraphRetriever validates graph path source chunks against the active permission scope.
- FastAPI routes gain authentication dependencies for protected endpoints while `/health` remains public.
- Agentic retrieval trace changes from a placeholder permission step to a real scope-check step.
- Tests need coverage for token auth, tenant isolation, KB-level access, retrieval filtering, and compatibility mode.
