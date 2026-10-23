# AI-Powered Document Assistant

Upload PDF, DOCX, and TXT documents, ask questions about their content, and get
answers grounded in the source files with citations.

This repository is built incrementally in six phases. The current state covers
**Phase 1 - Project foundation**.

## Status

| Phase | Scope | Status |
| --- | --- | --- |
| 1.1 | Project setup and runnable frontend/backend | Complete |
| 1.2 | Frontend layout, navigation, components, placeholder pages | Complete |
| 1.3 | Backend configuration, PostgreSQL, models, migrations, API contracts | Complete |
| 2 | Document ingestion (upload, validation, ownership, storage) | In progress |
| 3 | AI and retrieval pipeline | Planned |
| 4 | User-facing AI features | Planned |
| 5 | Security, testing, reliability | Planned |
| 6 | Deployment and delivery | Planned |

## Technology stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI
- **Database:** PostgreSQL (Phase 1.3)
- **Vector search:** pgvector (Phase 3)
- **Document parsing:** PyMuPDF, python-docx (Phase 2)
- **AI:** configurable LLM and embedding provider accessed through the backend (Phase 3)
- **Testing:** Pytest, Vitest and Testing Library
- **Deployment:** Docker and Docker Compose (Phase 6)

## Repository structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP routes
│   │   ├── core/         # Configuration, error handling, shared utilities
│   │   ├── db/           # Engine, session factory, declarative base
│   │   ├── models/       # Database models
│   │   ├── schemas/      # Request/response schemas
│   │   ├── services/     # Business logic
│   │   └── main.py       # FastAPI application factory
│   ├── alembic/          # Database migrations
│   ├── tests/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── hooks/
│   │   └── types/
│   ├── package.json
│   └── .env.example
├── docs/
│   ├── architecture.md
│   └── api.md
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.12+
- PostgreSQL 16 with pgvector (only needed from Phase 1.3 onward)
- Docker Desktop (optional but recommended for PostgreSQL)

## Local setup

All commands below are for **Windows PowerShell**.

### 1. Database

Start PostgreSQL 16 with pgvector using Docker Compose:

```powershell
docker compose up -d db
```

The container exposes PostgreSQL on `localhost:5433` with:

- User: `postgres`
- Password: `postgres`
- Database: `ai_document_assistant`

If you prefer an existing PostgreSQL instance, create the database and set
`DATABASE_URL` accordingly in `backend/.env`.

### 2. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The API is available at:

- Health check: <http://localhost:8000/api/health>
- OpenAPI docs: <http://localhost:8000/docs>

### 3. Frontend

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The app is available at <http://localhost:5173>.

## Verification

```powershell
# Backend tests
cd backend
.\.venv\Scripts\Activate.ps1
pytest
ruff check .

# Frontend checks
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

### Uploads

- Stored files live under `backend/uploads/` by owner and are gitignored.
- Supported types: `PDF`, `DOCX`, `TXT`. Validation inspects file content
  (magic bytes/ZIP structure) in addition to the extension.
- Uploads are owned by the development user until Phase 5 authentication.

Migration commands:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head      # apply migrations
alembic downgrade -1      # roll back one revision
alembic current           # show the applied revision
```

## Environment variables

### Backend (`backend/.env`)

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `AI-Powered Document Assistant` | Display name used in responses |
| `APP_VERSION` | `0.1.0` | Reported service version |
| `ENVIRONMENT` | `development` | Environment name |
| `API_PREFIX` | `/api` | Prefix for all API routes |
| `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed browser origins (JSON array) |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5433/ai_document_assistant` | SQLAlchemy database URL |
| `DB_ECHO` | `false` | Log SQL statements |
| `DB_POOL_PRE_PING` | `true` | Validate pooled connections before use |
| `DB_CONNECT_TIMEOUT_SECONDS` | `5` | PostgreSQL connect timeout |
| `UPLOAD_DIR` | `uploads` | Directory for stored uploads (relative to the backend working directory) |
| `MAX_UPLOAD_SIZE_MB` | `20` | Maximum upload size in megabytes |
| `ALLOWED_FILE_TYPES` | `["pdf","docx","txt"]` | Allowed file extensions (JSON array) |
| `DEV_USER_EMAIL` | `dev@local.test` | Development user email used until Phase 5 authentication |
| `DEV_USER_NAME` | `Development User` | Display name for the development user |

Never commit a real `.env` file. Only `.env.example` files belong in Git.

### Frontend (`frontend/.env`)

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL used by the UI |

## Development workflow

- `main` is the stable branch.
- `dev` is the integration branch.
- Each phase task is implemented on its own branch and merged through a pull request.
- A phase starts only after the previous phase's acceptance criteria pass.

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api.md)
