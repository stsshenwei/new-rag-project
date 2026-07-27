## ADDED Requirements

### Requirement: API token authentication
The system SHALL authenticate protected backend API requests using bearer API tokens when authentication is enabled.

#### Scenario: Missing token is rejected
- **WHEN** authentication is enabled and a protected endpoint receives no bearer token
- **THEN** the system SHALL reject the request with an unauthorized response.

#### Scenario: Invalid token is rejected
- **WHEN** authentication is enabled and a protected endpoint receives an unknown or revoked bearer token
- **THEN** the system SHALL reject the request with an unauthorized response.

#### Scenario: Valid token resolves principal
- **WHEN** authentication is enabled and a protected endpoint receives a valid bearer token
- **THEN** the system SHALL resolve the token to a principal, tenant context, roles, and allowed knowledge base ids.

### Requirement: Tenant and knowledge base model
The system SHALL persist users, tenants, teams, knowledge bases, tenant memberships, knowledge base memberships, and API tokens.

#### Scenario: Knowledge base belongs to tenant
- **WHEN** a knowledge base is created
- **THEN** the system SHALL store the tenant id, name, description, status, creator, and timestamps for that knowledge base.

#### Scenario: User has tenant role
- **WHEN** a user is added to a tenant
- **THEN** the system SHALL store the user id, tenant id, role, status, and timestamps for the membership.

#### Scenario: User has knowledge base role
- **WHEN** a user is granted access to a knowledge base
- **THEN** the system SHALL store the user id, tenant id, knowledge base id, role, status, and timestamps for the membership.

### Requirement: Permission scope resolution
The system SHALL resolve a `PermissionScope` for each protected request before executing business logic.

#### Scenario: Scope includes allowed knowledge bases
- **WHEN** a valid principal calls a protected endpoint
- **THEN** the resolved scope SHALL include the tenant id and the knowledge base ids the principal may access.

#### Scenario: Requested knowledge base is unauthorized
- **WHEN** a principal requests a knowledge base outside the resolved scope
- **THEN** the system SHALL reject the request as forbidden before retrieving documents, chunks, vectors, or graph evidence.

#### Scenario: Requested documents are narrowed by scope
- **WHEN** a request includes document ids
- **THEN** the resolved scope SHALL keep only document ids that belong to accessible knowledge bases or reject the request if any requested document is unauthorized.

### Requirement: Role based operations
The system SHALL authorize operations using tenant and knowledge base roles.

#### Scenario: Viewer can query
- **WHEN** a user has viewer access to a knowledge base
- **THEN** the system SHALL allow query, chat, document listing, and document content access for that knowledge base.

#### Scenario: Editor can ingest
- **WHEN** a user has editor or owner access to a knowledge base
- **THEN** the system SHALL allow document upload and ingest for that knowledge base.

#### Scenario: Viewer cannot mutate documents
- **WHEN** a user only has viewer access to a knowledge base
- **THEN** the system SHALL reject document upload, ingest, deletion, and membership mutation for that knowledge base.

#### Scenario: Knowledge base owner can manage members
- **WHEN** a user has owner access to a knowledge base
- **THEN** the system SHALL allow adding, updating, and removing knowledge base members.

### Requirement: Local single-tenant compatibility
The system SHALL preserve local single-tenant behavior when authentication is disabled.

#### Scenario: Auth disabled uses default scope
- **WHEN** `AUTH_ENABLED=false`
- **THEN** the system SHALL create or use a default local principal, tenant, and knowledge base permission scope.

#### Scenario: Existing APIs continue without token in local mode
- **WHEN** `AUTH_ENABLED=false` and a protected endpoint receives no bearer token
- **THEN** the system SHALL execute using the default local permission scope.

#### Scenario: Local mode marks trace metadata
- **WHEN** an Agent workflow runs with authentication disabled
- **THEN** the permission trace metadata SHALL indicate that compatibility mode was used.

### Requirement: Token safety
The system SHALL store and expose API tokens safely.

#### Scenario: Token hash is persisted
- **WHEN** an API token is created
- **THEN** the system SHALL persist only a token hash and token metadata, not the raw token value.

#### Scenario: Raw token is returned once
- **WHEN** an API token is created successfully
- **THEN** the system SHALL return the raw token only in the creation response.

#### Scenario: Trace does not expose token
- **WHEN** a request emits debug info, logs, or agent trace metadata
- **THEN** the system SHALL NOT include the raw bearer token.
