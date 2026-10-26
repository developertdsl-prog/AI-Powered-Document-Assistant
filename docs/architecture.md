# Architecture

## Overview

The AI-Powered Document Assistant is a web application with a React frontend and
a FastAPI backend. The backend owns authentication, document storage, document
processing, retrieval, and AI provider access so that no secrets or privileged
operations live in the browser.

## System context

```
Browser (React SPA)
        |
        | HTTPS / JSON
        v
FastAPI application
        |
        +-- PostgreSQL        (metadata, conversations, document records)
        +-- Vector store      (pgvector, Phase 3)
        +-- File storage      (local disk in development, object storage in production)
        +-- LLM / embeddings  (external provider through the backend only)
```

## Backend layering

| Layer | Location | Responsibility |
| --- | --- | --- |
| API routes | `backend/app/api/` | HTTP concerns, request validation, response shaping |
| Schemas | `backend/app/schemas/` | Pydantic request/response models |
| Services | `backend/app/services/` | Business logic, parsing, retrieval, AI calls |
| Models | `backend/app/models/` | Persistence models |
| Database | `backend/app/db/` | Engine, session factory, declarative base |
| Migrations | `backend/alembic/` | Versioned schema changes |
| Core | `backend/app/core/` | Configuration, logging, security, error handling |

Rules:

- Routes do not contain business logic; they delegate to services.
- Services never build HTTP responses; they raise domain errors.
- Configuration is read from the environment through a single settings object.
- Documents are treated as untrusted input. Text inside a document never
  overrides system instructions.

## Frontend layering

| Layer | Location | Responsibility |
| --- | --- | --- |
| Pages | `frontend/src/pages/` | Route-level screens |
| Components | `frontend/src/components/` | Reusable presentation components |
| Services | `frontend/src/services/` | API client modules |
| Hooks | `frontend/src/hooks/` | Reusable stateful logic |
| Types | `frontend/src/types/` | Shared TypeScript types |

The frontend communicates with the backend exclusively through documented APIs
(`/api/...`). It never holds provider API keys.

## Configuration

Backend settings are defined in `backend/app/core/config.py` using
`pydantic-settings` and loaded from environment variables or `backend/.env`.
Frontend configuration is limited to `VITE_*` variables, which are public by
definition. No secret may be exposed through a `VITE_` variable.

## Error format

Phase 1.1 establishes a single error envelope. It is documented and finalized in
Phase 1.3.

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found.",
    "details": null
  }
}
```

## Database

PostgreSQL is the only supported production database. SQLAlchemy 2.x is used
with the synchronous `psycopg` driver (`postgresql+psycopg://`). The engine is
created once in `backend/app/db/session.py` with `pool_pre_ping` enabled and a
configurable connect timeout. Requests obtain sessions through the `get_db`
dependency; sessions are always closed.

Schema changes are versioned with Alembic (`backend/alembic/versions`). The
initial migration creates `users`, `documents`, `document_chunks`,
`conversations`, and `messages`. Migrations are the only supported way to change
production schemas; `Base.metadata.create_all` is used in tests only.

The test database can be SQLite in memory because the models use portable
types (`Uuid`, `JSON`, `String`). The JSONB/pgvector-specific columns are
introduced in Phase 3, together with PostgreSQL-only tests.

## Health checks

`GET /api/health` reports the service status, version, environment, and database
connectivity. It executes `SELECT 1` and returns `200` with `database: "up"`
when the database is reachable, or `503` with `status: "degraded"` and
`database: "down"` when it is not. The endpoint never crashes when the database
is offline.

## Phase roadmap

- Phase 1: foundation, frontend shell, database models and API contracts.
- Phase 2: upload, parsing, metadata, processing status, and error handling.
- Phase 3: chunking, embeddings, pgvector retrieval, grounded answer generation.
- Phase 4: chat, summarization, extraction, document library and history.
- Phase 5: authentication, authorization, automated tests, reliability.
- Phase 6: containerization, deployment, documentation and acceptance.
