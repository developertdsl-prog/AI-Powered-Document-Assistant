# AI-Powered Document Assistant

Upload PDF, DOCX, and TXT documents, ask questions about their content, and get
answers grounded in the source files with citations.

This repository is built incrementally in six phases. The current state covers
**Phase 3 - AI and retrieval pipeline**: chunking, embeddings, similarity
search, and grounded answer generation. **Phase 4 - User-facing AI features**
is next.

## Status

| Phase | Scope | Status |
| --- | --- | --- |
| 1.1 | Project setup and runnable frontend/backend | Complete |
| 1.2 | Frontend layout, navigation, components, placeholder pages | Complete |
| 1.3 | Backend configuration, PostgreSQL, models, migrations, API contracts | Complete |
| 2.1 | Upload UI with drag-and-drop, progress, and status | Complete |
| 2.2 | Upload API, validation, ownership, and storage | Complete |
| 2.3 | Parsing, metadata, processing status, and error handling | Complete |
| 3.1 | Paragraph-aware chunking pipeline | Complete |
| 3.2 | pgvector embeddings for document chunks | Complete |
| 3.3 | Similarity search over embedded chunks | Complete |
| 3.4 | Grounded answer generation with citations | Complete |
| 4 | User-facing AI features | Next |
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

### Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs the same checks on every pull
request into `dev` or `main` and on pushes to those branches:

- **Backend checks** - `ruff check .` and `pytest`.
- **PostgreSQL migrations** - replays every Alembic migration up and down
  against a `pgvector/pgvector:pg16` service, verifying the `vector` extension
  and the HNSW cosine index that SQLite cannot create
  (`TEST_DATABASE_URL`; skipped when unset, e.g. in local runs).
- **Frontend checks** - `npm run typecheck`, `npm run lint`, `npm test`.

Runs for the same branch or pull request cancel automatically when a newer
push arrives, and every job has a timeout.

### Uploads and processing

- Stored files live under `backend/uploads/` by owner and are gitignored.
- Supported types: `PDF`, `DOCX`, `TXT`. Validation inspects file content
  (magic bytes/ZIP structure) in addition to the extension.
- Uploads are owned by the development user until Phase 5 authentication.
- Uploaded documents are processed in the background by default. PDF pages keep
  their real page numbers, DOCX uses one logical page because DOCX has no fixed
  pagination, and TXT files split on form-feed characters.
- Processing records `processing`, then `ready` or `failed`, with metadata,
  page text, and a user-facing error message. Set
  `PROCESS_UPLOADS_IN_BACKGROUND=false` to process synchronously in the upload
  request (useful for debugging).
- Processing also splits the extracted pages into overlapping, paragraph-aware
  chunks (`CHUNK_SIZE_CHARS`, default 1000 characters; `CHUNK_OVERLAP_CHARS`,
  default 150) stored in `document_chunks`. These chunks are the retrieval unit
  for the Phase 3 search and answer pipeline.
- Each chunk is embedded into a 1536-wide pgvector vector during processing
  (`EMBEDDING_PROVIDER`, default `auto`: OpenAI when `OPENAI_API_KEY` is set,
  otherwise a deterministic offline hash provider; `none` skips vectors).
  The chosen provider is recorded in the document's metadata, and an
  embedding failure marks the document `failed` with a user-facing message.
- Questions are answered from retrieved evidence only
  (`POST /api/documents/{id}/answers`). `LLM_PROVIDER` defaults to `auto`:
  an OpenAI-compatible chat model when `OPENAI_API_KEY` is set, otherwise an
  offline extractive provider that quotes the matching sentences. Every reply
  cites the passages it used, citations the model invents are dropped, and a
  question with no supporting passage returns a fixed refusal with
  `grounded: false`.

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
| `PROCESS_UPLOADS_IN_BACKGROUND` | `true` | Parse uploads in a background task; set `false` to parse during the upload request |
| `CHUNK_SIZE_CHARS` | `1000` | Target size of a retrieval chunk in characters |
| `CHUNK_OVERLAP_CHARS` | `150` | Characters carried from one chunk into the next |
| `EMBEDDING_PROVIDER` | `auto` | `auto` (OpenAI when a key is set, otherwise offline hash), `openai`, `hash`, or `none` |
| `EMBEDDING_BATCH_SIZE` | `100` | Texts sent per embeddings API request |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | Embeddings request timeout |
| `OPENAI_API_KEY` | _(unset)_ | API key for the OpenAI-compatible embeddings endpoint |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL of the embeddings endpoint (OpenAI-compatible services work here) |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model; width must stay 1536 to match the schema |
| `LLM_PROVIDER` | `auto` | `auto` (OpenAI when a key is set, otherwise offline extractive answers), `openai`, `extractive`, or `none` |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model used for grounded answers |
| `LLM_MAX_TOKENS` | `700` | Maximum tokens requested per answer |
| `LLM_TIMEOUT_SECONDS` | `60` | Answer provider request timeout |
| `ANSWER_CONTEXT_CHUNKS` | `6` | Passages retrieved as evidence when the request omits `limit` |
| `ANSWER_MIN_SIMILARITY` | `0.0` | Drop evidence below this cosine score; keep `0.0` with the offline hash embeddings, whose scores are not comparable |
| `ANSWER_MAX_CONTEXT_CHARS` | `8000` | Character budget for the passages sent to the model |
| `ANSWER_EXCERPT_CHARS` | `300` | Length of the `excerpt` returned with each citation |

Never commit a real `.env` file. Only `.env.example` files belong in Git.

### Frontend (`frontend/.env`)

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL used by the UI |

## Development workflow

- `main` is the stable branch.
- `dev` is the integration branch.
- Each phase task is implemented on its own branch, then committed, pushed, and
  merged into `dev` before the next branch starts. Each merge is tagged as a
  milestone (see [Milestones](docs/milestones.md)).
- A phase starts only after the previous phase's acceptance criteria pass.

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api.md)
- [Milestones](docs/milestones.md)
