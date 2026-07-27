## Context

**Dependency:** this change SHALL be applied after `add-multi-knowledge-base-domain`. The existing `workspace`, `knowledge_base`, `KnowledgeBaseScope`, document/chunk ownership, scoped Milvus/FTS/KG retrieval, lifecycle API, and management UI are authoritative. This change must not create competing knowledge-base tables, IDs, migrations, or UI.

The backend has grown from a single Raw RAG path into a layered knowledge system with document/chunk storage, SQLite FTS5, Milvus vector retrieval, optional Neo4j graph retrieval, KG extraction, conversation memory, agentic workflow, and evaluation. `add-multi-knowledge-base-domain` already makes workspace/KB ownership authoritative across those stores. The remaining gap is caller authorization: protected routes do not authenticate a principal, and `AgenticRetrievalWorkflow.CheckPermissionScope` does not yet intersect requested KBs with membership permissions.

This change introduces the permission boundary needed before the system can be safely used as an enterprise knowledge base. It must protect both direct HTTP document APIs and indirect retrieval performed by tools inside the Agent FSM.

## Goals / Non-Goals

**Goals:**

- Add backend authentication using API tokens.
- Add users, tenants, teams, membership roles, and API token persistence while reusing the existing knowledge-base domain.
- Resolve every protected request into a `PermissionScope`.
- Resolve `PermissionScope` and intersect it with the already persisted `KnowledgeBaseScope` before evidence access.
- Enforce the active scope across document APIs, Raw RAG, SQLite FTS5, Milvus retrieval, GraphRetriever, `/rag/query`, and `/chat/stream`.
- Keep a compatibility mode for current local single-tenant development.
- Keep provider boundaries explicit so auth, token storage, and permission checks can be replaced later.

**Non-Goals:**

- No frontend login or account management UI.
- No OAuth, SSO, SAML, LDAP, password reset, or multi-factor authentication.
- No field-level ACLs inside documents or chunks.
- No full migration from SQLite to Postgres/MySQL.
- No document download watermarking or advanced audit dashboards.
- No graph review UI or chunk governance UI.

## Decisions

### Use API Token Auth For The First Permission Layer

Protected backend routes will accept bearer API tokens. Tokens map to a user and tenant context, and token hashes are stored instead of raw token values.

Rationale: API tokens let the backend enforce permissions without blocking this change on frontend session UX. They also work for SDKs, eval runners, and internal service calls.

Alternative considered: implement username/password login now. Rejected because it expands scope into frontend state, sessions, password security, reset flows, and user lifecycle before retrieval isolation is solved.

### Model Tenant And Knowledge Base Membership Separately

Tenant membership grants organization-level access. Knowledge base membership grants access to a specific corpus. A user may belong to a tenant but only see selected knowledge bases.

Initial roles:

- Tenant: `owner`, `admin`, `member`, `viewer`
- Knowledge base: `owner`, `editor`, `viewer`

Rationale: Enterprise KB isolation usually sits at the knowledge base level, not just tenant level. Separating these roles gives enough structure for upload, ingest, delete, and query authorization without overbuilding IAM.

Alternative considered: one global user role. Rejected because it cannot express "can use this KB but not that KB."

### Introduce A PermissionScope Object

Each protected route resolves a `PermissionScope` before calling service methods. The scope includes:

- `principal_id`
- `tenant_id`
- allowed knowledge base ids
- allowed document ids if a request narrows access
- role metadata
- compatibility-mode marker when auth is disabled

Rationale: A single scope object can move through RAG service, retrieval tools, repositories, vector store, and GraphRetriever without each layer re-parsing HTTP auth.

Alternative considered: checking permission only in FastAPI routes. Rejected because Agent tools and service methods can be invoked internally and would become bypass paths.

### Enforce Scope At Every Evidence Boundary

Permission filtering must happen where evidence is retrieved:

- SQLite document and chunk queries use the authorized existing `workspace_id`, `knowledge_base_id`, and optional doc ids.
- SQLite FTS5 joins to authoritative chunk rows and filters by the same scope.
- Milvus vector rows keep the existing workspace/KB ownership from the prerequisite change, and vector/BM25 queries receive the authorized intersection as filter expressions.
- GraphRetriever validates every returned relation source chunk with the evidence repository and active scope.
- Citation verification only accepts chunks visible in scope.

Rationale: Filtering only after retrieval can leak result existence, graph metadata, scores, or citations from unauthorized corpora.

Alternative considered: retrieve globally and drop unauthorized chunks later. Rejected because it can leak metadata and corrupt ranking.

### Keep Local Single-Tenant Compatibility

When `AUTH_ENABLED=false`, the backend creates or assumes default ids:

- `DEFAULT_TENANT_ID=default`
- the existing `DEFAULT_WORKSPACE_ID` and `DEFAULT_KNOWLEDGE_BASE_ID`
- `DEFAULT_USER_ID=local-dev`

Existing upload, ingest, query, chat, memory, and eval flows continue to work without a token.

Rationale: The project currently relies on local development and tests without auth headers. Compatibility mode keeps the change deployable and lets permission enforcement be tested independently.

Alternative considered: make auth mandatory immediately. Rejected because it would break existing local workflows and tests before users have a login UI.

### Keep Provider Interfaces Replaceable

The implementation should define interfaces such as:

- `AuthProvider`
- `ApiTokenProvider`
- `PermissionProvider`
- `PermissionScopeResolver`

Initial implementations can use SQLite. Later changes can swap in external IAM, OAuth, SSO, or a centralized policy engine.

Rationale: The project already prefers provider interfaces for LLMs, embeddings, graph stores, and vector stores. Auth should follow the same pattern.

## Risks / Trade-offs

- The prerequisite final storage schema may be missing or in maintenance -> Honor its `reset_required`/maintenance failure and do not attempt an auth-side migration.
- Tenant membership may diverge from workspace ownership -> Persist an explicit tenant-to-workspace mapping and always derive authorized KB IDs before evidence access.
- GraphRetriever could return relations from unauthorized chunks -> Require source chunk scope validation before relation/path output.
- Agent tools may be called without scope by tests or internal code -> Provide explicit compatibility scope when auth is disabled and fail closed when auth is enabled.
- API tokens without a UI are less friendly for end users -> Accept this for the backend foundation and leave login UI for a later change.
- Adding auth to eval endpoints may complicate automated evaluation -> Eval runner should accept a system or configured token/scope and record it in debug metadata.

## Initialization Plan

1. Require the completed final schema from `add-multi-knowledge-base-domain`; do not alter or backfill evidence ownership.
2. Add auth and permission tables with idempotent auth-schema initialization.
3. Create a default tenant and local-dev user when compatibility mode is enabled; map permissions to the existing default workspace/KB IDs.
4. Reuse existing document, chunk, Milvus, FTS5, KG, and graph knowledge-base ownership without schema duplication.
5. Resolve permissions and intersect allowed KB IDs with the request's `KnowledgeBaseScope`.
6. Fail closed when the permission intersection is empty.
7. Add route dependencies that resolve a `PermissionScope`.
8. Thread scope through RAG service, retrieval tools, repositories, vector store, graph retriever, and citation verifier.
9. Keep `AUTH_ENABLED=false` as the default for local development unless explicitly configured otherwise.

Rollback strategy: disable auth with `AUTH_ENABLED=false` and continue using the existing default workspace/KB scope. Auth rollback does not reindex, migrate, or mutate knowledge storage.

## Open Questions

- Should API tokens be scoped to a single tenant only, or can one token represent a user across multiple tenants?
- Should evaluation runs be tenant-scoped user operations or admin/system operations?
- Should conversation memory be scoped by user only, by tenant, or by knowledge base in this change?
- Should feedback-generated documents inherit the active knowledge base or write to a dedicated feedback knowledge base?
