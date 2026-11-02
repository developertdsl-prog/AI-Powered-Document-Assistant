# API contract

Base URL in development: `http://localhost:8000`
API prefix: `/api`

OpenAPI is generated automatically:

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- Schema: `GET /openapi.json`

## Conventions

| Concern | Convention |
| --- | --- |
| Content type | `application/json` unless stated otherwise |
| Identifiers | UUID v4 strings |
| Timestamps | ISO 8601 with UTC timezone (`2026-10-23T09:42:00Z`) |
| Field naming | `snake_case` in JSON |
| Authentication | JWT bearer tokens: `POST /api/auth/register`, `POST /api/auth/login`, then `Authorization: Bearer <token>` on every protected request |
| Document ownership | Every document record has `owner_id`; document, conversation, and insight queries are scoped to the user behind the bearer token |

## Error envelope

All non-2xx responses use one envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found.",
    "details": null
  }
}
```

`details` carries structured information for validation errors and is `null` otherwise.

### Error codes

| HTTP | `code` | Meaning |
| --- | --- | --- |
| 400 | `bad_request` | Malformed request |
| 401 | `unauthorized` | Missing, malformed, expired, or rejected credentials |
| 403 | `forbidden` | Authenticated but not allowed |
| 404 | `not_found` | Resource does not exist |
| 405 | `method_not_allowed` | Method not supported for this path |
| 409 | `conflict` | State conflict (for example a duplicate email) |
| 409 | `document_not_ready` | Extracted text was requested before processing finished |
| 409 | `embeddings_unavailable` | Embeddings are disabled, so retrieval cannot run |
| 409 | `answers_unavailable` | Answer, summary, or extraction generation is disabled on this server (`LLM_PROVIDER=none`) |
| 413 | `file_too_large` | Upload exceeds the configured limit (Phase 2) |
| 415 | `unsupported_media_type` | File type is not allowed (Phase 2) |
| 422 | `validation_error` | Request body or query validation failed |
| 429 | `rate_limited` | Per-user rate limit exceeded on an upload or AI endpoint (see [Rate limits](#rate-limits)) |
| 500 | `internal_error` | Unexpected server failure |
| 503 | `service_unavailable` | A required dependency is unavailable |

Validation example (`422`):

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [
      {
        "type": "missing",
        "loc": ["body", "email"],
        "msg": "Field required",
        "input": {}
      }
    ]
  }
}
```

## Authentication

Every endpoint except `GET /api/health`, `POST /api/auth/register`, and
`POST /api/auth/login` requires a bearer token. Requests without one answer
`401 unauthorized` in the standard envelope.

### `POST /api/auth/register`

Create an account.

**Request:**

```json
{
  "email": "ada@example.com",
  "password": "correct-horse-battery",
  "full_name": "Ada Lovelace"
}
```

| Name | Type | Notes |
| --- | --- | --- |
| `email` | string | Required, 3 to 254 characters; trimmed and lowercased, must look like an address |
| `password` | string | Required, 8 to 72 characters (the bcrypt input limit) |
| `full_name` | string | Optional, at most 120 characters |

**201 Created:**

```json
{
  "id": "3f1c5f9c-3d0e-4a63-9d6f-2b0a1c6f9a11",
  "email": "ada@example.com",
  "full_name": "Ada Lovelace",
  "created_at": "2026-11-02T09:42:00Z"
}
```

Passwords are hashed with bcrypt and a per-password salt; the hash is never
returned. Registration does not issue a token, so sign in afterwards.

**Errors:** `409 conflict` when the email already exists,
`422 validation_error` for an invalid email or a password outside 8-72
characters.

### `POST /api/auth/login`

Exchange credentials for an access token.

**Request:** `{ "email": "ada@example.com", "password": "correct-horse-battery" }`

**200 OK:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

The token is a signed JWT (`JWT_ALGORITHM`, default `HS256`) whose `sub` claim
is the user id and whose `exp` claim is `ACCESS_TOKEN_EXPIRE_MINUTES` (default
60) after issue. Send it as `Authorization: Bearer <token>`.

**Errors:** `401 unauthorized` with the message `Incorrect email or password.`
for a wrong password, an unknown email, or a disabled account - the same
message for all three, so the endpoint cannot be used to enumerate accounts.

### `GET /api/auth/me`

Describe the account behind the request's token.

**200 OK:** the same user object as registration.

**Errors:** `401 unauthorized` for a missing, malformed, expired, or
wrong-secret token, and for a token whose account was deleted or disabled.

## Rate limits

Upload and AI endpoints count requests per user in a fixed window
(`RATE_LIMIT_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS`, defaults 60 per 60
seconds) and answer `429 rate_limited` when the window's allowance is used up:

- `upload` bucket: `POST /api/documents`
- `ai` bucket: `POST /api/documents/{id}/search`,
  `POST /api/documents/{id}/answers`, `POST /api/conversations/{id}/messages`,
  `POST /api/documents/{id}/summaries`, `POST /api/documents/{id}/extractions`

The buckets are separate, so a burst of uploads does not consume the allowance
for questions. Counters live in process memory, which is correct for one
backend process; a shared store is a Phase 6 concern. Set
`RATE_LIMIT_ENABLED=false` to turn the limits off.

## Implemented endpoints

### `GET /api/health`

Reports API status and verifies the database with `SELECT 1`.

**200 OK** when the API and database are healthy:

```json
{
  "status": "ok",
  "service": "AI-Powered Document Assistant",
  "version": "0.1.0",
  "environment": "development",
  "database": "up",
  "checked_at": "2026-10-23T09:42:00Z"
}
```

**503 Service Unavailable** when the API is running but the database is not
reachable. The payload uses the same health schema, with `status` set to
`degraded` and `database` set to `down`.

### `POST /api/documents`

Upload a `PDF`, `DOCX`, or `TXT` file via `multipart/form-data`. The request
uses the form field `file`.

**Validation and storage:**

- Maximum size: `20 MB` (configurable with `MAX_UPLOAD_SIZE_MB`)
- Allowed extensions: `pdf`, `docx`, `txt`
- Content is sniffed by magic bytes (PDF header, ZIP structure for DOCX,
  null-byte checks for text files). Extension alone is not trusted.
- Files are stored under `uploads/{owner_id}/` with a generated name. The
  `storage_path` is not exposed in responses.
- A SHA-256 checksum is computed while streaming.
- Documents are created with `status` set to `pending`. Text extraction runs in
  a background task by default and moves the document to `processing`, then
  `ready` or `failed`. Set `PROCESS_UPLOADS_IN_BACKGROUND=false` to extract text
  before the upload response returns.

**200/201 response:**

```json
{
  "id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "original_filename": "Quarterly Report.pdf",
  "content_type": "application/pdf",
  "file_size_bytes": 245186,
  "checksum": "7f3e...",
  "status": "pending",
  "page_count": null,
  "error_message": null,
  "created_at": "2026-10-23T10:12:00Z",
  "updated_at": "2026-10-23T10:12:00Z"
}
```

**Errors:**

| Status | Code | When |
| --- | --- | --- |
| 413 | `file_too_large` | File exceeds `MAX_UPLOAD_SIZE_MB` |
| 415 | `unsupported_media_type` | Unsupported extension, mismatch between extension and content, or invalid file structure |
| 422 | `validation_error` | Missing file, empty file, or path traversal resulted in an invalid filename |

All protected endpoints require a bearer token; the document is stored under
the authenticated owner's directory.

### `GET /api/documents`

List documents owned by the current user.

**Query parameters:**

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `limit` | integer | `50` | `1` to `100` |
| `offset` | integer | `0` | `>= 0` |
| `q` | string | none | Case-insensitive substring the filename must contain; `422` above 200 characters |

LIKE wildcards (`%`, `_`) in `q` are matched literally, so `q=50%` finds the
filename `50%-discount.txt` and nothing else. `total` reflects the same
filter, so pagination and match counts stay consistent. A blank `q` is
ignored.

**200 OK:**

```json
{
  "items": [
    {
      "id": "...",
      "original_filename": "Notes.txt",
      "content_type": "text/plain",
      "file_size_bytes": 1245,
      "checksum": "...",
      "status": "pending",
      "page_count": null,
      "error_message": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 1
}
```

### `GET /api/documents/{id}`

Get one document owned by the current user.

**404 Not Found** when the document does not exist or belongs to another
user. The response uses the standard error envelope.

### `DELETE /api/documents/{id}`

Delete a document owned by the current user, together with its stored file,
extracted pages, chunks, conversations, and messages. A failed upload can be
cleaned up as easily as a ready one.

**200 OK:**

```json
{ "message": "Document deleted." }
```

**Errors:** `404` when the document does not exist or belongs to another
user; `422` for a malformed id.

Deleting a document while its background processing is still running is
allowed. The task re-reads the document and stops when it is gone; one
already past that check fails on the missing rows without corrupting
anything.

### `GET /api/documents/{id}/text`

Return extracted text and processing metadata for a document owned by the
current user. Text is split into pages in reading order.

**200 OK:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "status": "ready",
  "page_count": 2,
  "metadata": {
    "format": "pdf",
    "page_count": 2,
    "text_characters": 412,
    "title": "Quarterly Report",
    "author": null,
    "producer": "PyMuPDF",
    "creation_date": "D:20261023101200Z"
  },
  "pages": [
    {
      "page_number": 1,
      "content": "Quarterly report page one.",
      "character_count": 26,
      "metadata": {
        "width": 612.0,
        "height": 792.0,
        "link_count": 0
      }
    }
  ]
}
```

**Page numbering:**

- PDF: real page numbers from the file.
- DOCX: one logical page (`page_number: 1`) with
  `metadata.page_numbering` set to `unavailable`; DOCX has no fixed pagination.
- TXT: one page, or multiple pages when form-feed (`\f`) separators are present.
  `metadata.page_numbering` is `single_page` or `form_feed`.

**Errors:**

| Status | Code | When |
| --- | --- | --- |
| 404 | `not_found` | Document does not exist or belongs to another user |
| 409 | `document_not_ready` | Document is `pending`, `processing`, or `failed` |

**Processing failures** are stored on the document as `error_message` and keep
the document in `failed` status. Failures include corrupt files, password
protected or text-free PDFs, empty documents, and missing stored files. Scanned
PDFs are not OCR'd in this phase.

**Processing metadata** stored on the document includes the format, page count,
text length, and format-specific fields such as title, author, producer,
encoding, paragraph count, and table count.

### `POST /api/documents/{id}/search`

Embed the query with the provider selected by `EMBEDDING_PROVIDER` and return
the document's most similar chunks with cosine similarity scores. Only
documents in the `ready` state are searchable.

**Request:**

```json
{
  "query": "What is the refund policy?",
  "limit": 5
}
```

**200 OK:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "query": "What is the refund policy?",
  "results": [
    {
      "chunk_id": "3f0a9d2c-5f9a-4d0f-9a1e-2b7c8d6e5f41",
      "chunk_index": 4,
      "page_number": 2,
      "score": 0.8123,
      "content": "Refunds are issued within 14 days of purchase."
    }
  ]
}
```

**Errors:** `404` unknown or foreign document, `409` document not ready or
embeddings disabled, `422` blank query or `limit` outside 1-20.

### `POST /api/documents/{id}/answers`

Answer a question about a document using only passages retrieved from it
(grounded answer generation, Phase 3.4). Only documents in the `ready` state
can be asked.

**Request:**

```json
{
  "question": "What is the refund policy?",
  "limit": 6
}
```

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `question` | string | _(required)_ | 1 to 2000 characters, must not be blank |
| `limit` | integer | `6` | Passages retrieved as evidence, 1 to 20 |

**200 OK:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "question": "What is the refund policy?",
  "answer": "Refunds are issued within 14 days of purchase.",
  "grounded": true,
  "citations": [
    {
      "reference": 1,
      "chunk_id": "3f0a9d2c-5f9a-4d0f-9a1e-2b7c8d6e5f41",
      "chunk_index": 4,
      "page_number": 2,
      "score": 0.8123,
      "excerpt": "Refunds are issued within 14 days of purchase."
    }
  ],
  "provider": "extractive",
  "evidence_count": 5,
  "generated_at": "2026-10-29T09:42:00Z"
}
```

- `citations` reference the numbered passages supplied to the model. A number
  the model invented is dropped, so a citation always points at a real chunk.
- `grounded` is `true` when at least one passage supports the answer.
- When no passage supports the question, `answer` is the fixed refusal text
  ("The document does not contain enough information to answer this
  question."), `grounded` is `false`, and `citations` is empty.
- `provider` is the answering mode that produced the reply: `openai` for the
  configured OpenAI-compatible endpoint, `extractive` for the offline
  quotation fallback used when no API key is set.
- `evidence_count` is how many passages were retrieved, cited or not.
- Document text is untrusted input: the prompt instructs the model to ignore
  instructions found inside the document.

**Errors:**

| Status | Code | When |
| --- | --- | --- |
| 404 | `not_found` | Document does not exist or belongs to another user |
| 409 | `document_not_ready` | Document is `pending`, `processing`, or `failed` |
| 409 | `embeddings_unavailable` | Embeddings are disabled, so evidence cannot be retrieved |
| 409 | `answers_unavailable` | `LLM_PROVIDER=none` disables answer generation |
| 422 | `validation_error` | Blank or oversized question, or `limit` outside 1-20 |
| 503 | `service_unavailable` | The configured answer provider failed or is misconfigured |

## Conversations

Conversation history for document chat (Phase 4.1). Every conversation belongs
to the current user and, for answering, to exactly one document. Another user's
conversation is indistinguishable from a missing one (`404`).

### `GET /api/conversations`

List the current user's conversations, most recently active first.

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `limit` | integer | `50` | Page size, 1 to 100 |
| `offset` | integer | `0` | Rows to skip |

**200 OK:**

```json
{
  "items": [
    {
      "id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
      "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
      "title": "What is the refund policy?",
      "created_at": "2026-10-29T09:40:00Z",
      "updated_at": "2026-10-29T09:42:00Z"
    }
  ],
  "total": 1
}
```

### `POST /api/conversations`

Start a conversation about a document owned by the current user. The document
must exist; it does not have to be `ready` yet (asking before processing
finishes returns `409`).

**Request:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "title": "Refund questions"
}
```

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `document_id` | UUID | _(required)_ | Document the conversation asks about |
| `title` | string | `New conversation` | 1 to 255 characters, must not be blank |

**201 Created** returns the conversation as shown above. Unless a title is
supplied, the first question asked retitles the conversation.

**Errors:** `404` unknown or foreign document, `422` blank title.

### `GET /api/conversations/{id}`

Return one conversation with its message history in reading order.

**200 OK:**

```json
{
  "id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "title": "What is the refund policy?",
  "created_at": "2026-10-29T09:40:00Z",
  "updated_at": "2026-10-29T09:42:00Z",
  "messages": [
    {
      "id": "0a5e2f77-93ab-4e4c-8a5d-4e8f0d2c6b91",
      "conversation_id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
      "role": "user",
      "content": "What is the refund policy?",
      "position": 1,
      "citations": [],
      "created_at": "2026-10-29T09:40:00Z"
    },
    {
      "id": "1b6f3a88-04bc-4f5d-9b6e-5f9a1e3d7c02",
      "conversation_id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
      "role": "assistant",
      "content": "Refunds are issued within 14 days of purchase.",
      "position": 2,
      "citations": [
        {
          "reference": 1,
          "chunk_id": "3f0a9d2c-5f9a-4d0f-9a1e-2b7c8d6e5f41",
          "chunk_index": 4,
          "page_number": 2,
          "score": 0.8123,
          "excerpt": "Refunds are issued within 14 days of purchase."
        }
      ],
      "created_at": "2026-10-29T09:42:00Z"
    }
  ]
}
```

- `position` is the message's order inside the conversation; use it instead of
  `created_at`, which can tie between a question and its reply.
- `citations` is empty for user turns; assistant turns cite the passages that
  support the answer, with the same semantics as
  `POST /api/documents/{id}/answers`.

**Errors:** `404` unknown or foreign conversation.

### `POST /api/conversations/{id}/messages`

Ask a question and receive a grounded, cited answer. Both turns are persisted,
so `GET /api/conversations/{id}` replays the full history. The answer pipeline
is the same as `POST /api/documents/{id}/answers` (retrieval, numbered
evidence, refusal when nothing supports the answer).

**Request:** the answers shape — `question` (required, 1 to 2000 characters)
and optional `limit` (1 to 20, default `6`).

**200 OK:**

```json
{
  "conversation_id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
  "user_message": {
    "id": "0a5e2f77-93ab-4e4c-8a5d-4e8f0d2c6b91",
    "conversation_id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
    "role": "user",
    "content": "What is the refund policy?",
    "position": 1,
    "citations": [],
    "created_at": "2026-10-29T09:40:00Z"
  },
  "assistant_message": {
    "id": "1b6f3a88-04bc-4f5d-9b6e-5f9a1e3d7c02",
    "conversation_id": "6c1b9c1e-7d5a-4c2e-9a63-2c5f0b1a8d44",
    "role": "assistant",
    "content": "Refunds are issued within 14 days of purchase.",
    "position": 2,
    "citations": [
      {
        "reference": 1,
        "chunk_id": "3f0a9d2c-5f9a-4d0f-9a1e-2b7c8d6e5f41",
        "chunk_index": 4,
        "page_number": 2,
        "score": 0.8123,
        "excerpt": "Refunds are issued within 14 days of purchase."
      }
    ],
    "created_at": "2026-10-29T09:42:00Z"
  }
}
```

Nothing is persisted when answer generation fails, so a `503` leaves the
history unchanged.

**Errors:**

| Status | Code | When |
| --- | --- | --- |
| 400 | `bad_request` | The conversation has no linked document |
| 404 | `not_found` | Conversation or its document does not exist or belongs to another user |
| 409 | `document_not_ready` | The linked document is `pending`, `processing`, or `failed` |
| 409 | `embeddings_unavailable` | Embeddings are disabled, so evidence cannot be retrieved |
| 409 | `answers_unavailable` | `LLM_PROVIDER=none` disables answer generation |
| 422 | `validation_error` | Blank or oversized question |
| 503 | `service_unavailable` | The configured answer provider failed or is misconfigured |

## Summaries and extraction

Summarization and structured extraction for one ready document (Phase 4.2).
Both read the document in order instead of retrieving, so they do not need
embeddings and keep working while `EMBEDDING_PROVIDER=none`. Ownership and
processing status are enforced exactly as for answers: another user's document
returns `404`, and a document that is not `ready` returns `409`.

Nothing is stored; every call generates a fresh result. The passages that fit
`SUMMARY_MAX_CONTEXT_CHARS` (default `12000`) are used, so `truncated` reports
that the document was longer than the budget.

### `POST /api/documents/{id}/summaries`

Summarize a ready document in reading order.

**Request:**

```json
{
  "length": "detailed"
}
```

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `length` | string | `concise` | `concise` (a few sentences) or `detailed` (the main ideas in short paragraphs) |

**200 OK:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "length": "concise",
  "summary": "Refunds are issued within 14 days of purchase.",
  "provider": "extractive",
  "source_chunks": 2,
  "truncated": false,
  "generated_at": "2026-10-29T10:00:00Z"
}
```

- `provider` is `extractive` for the offline provider that quotes the
  document's opening sentences, or `openai` for a configured model.
- `source_chunks` counts the passages used; a document without extractable
  text returns a summary saying so with `source_chunks` `0`.

**Errors:**

| Status | Code | When |
| --- | --- | --- |
| 404 | `not_found` | Document does not exist or belongs to another user |
| 409 | `document_not_ready` | Document is `pending`, `processing`, or `failed` |
| 409 | `answers_unavailable` | `LLM_PROVIDER=none` disables generation |
| 422 | `validation_error` | Unknown `length` value |
| 503 | `service_unavailable` | The configured provider failed or is misconfigured |

### `POST /api/documents/{id}/extractions`

Extract key points, dates, names, and any custom fields from a ready document.

**Request:**

```json
{
  "fields": ["Invoice number", "Due date"],
  "max_items": 10
}
```

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `fields` | array | `[]` | Custom field names of 1 to 60 characters; at most 10, duplicates collapse, blank names are rejected |
| `max_items` | integer | `10` | Items returned per collection (key points, dates, names), 1 to 25 |

**200 OK:**

```json
{
  "document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263",
  "key_points": ["Refunds are issued within 14 days of purchase."],
  "dates": ["March 3, 2026", "2026-04-01"],
  "names": ["Acme Corp"],
  "fields": [
    { "name": "Invoice number", "value": "INV-2024-015", "found": true },
    { "name": "Due date", "value": null, "found": false }
  ],
  "provider": "extractive",
  "source_chunks": 2,
  "truncated": false,
  "generated_at": "2026-10-29T10:00:00Z"
}
```

- Every requested field comes back in order with `found` `false` and `value`
  `null` when the document does not contain it.
- The offline provider quotes and pattern-matches the text (`name: value`
  forms for fields), so it never invents a value. With a model provider the
  reply must be one JSON object; anything else is reported as `503` instead of
  returning an empty extraction.

**Errors:** as for summaries, plus `422` for blank or oversized field names
and a `max_items` outside 1-25.

## Data model

```text
users
  id, email, full_name, hashed_password, is_active, created_at, updated_at

documents
  id, owner_id -> users.id, original_filename, storage_path, content_type,
  file_size_bytes, checksum, status, page_count, error_message,
  doc_metadata, processed_at, created_at, updated_at

document_pages
  id, document_id -> documents.id, page_number, content, character_count,
  page_metadata, created_at, updated_at
  unique(document_id, page_number)

document_chunks
  id, document_id -> documents.id, chunk_index, content, page_number,
  token_count, chunk_metadata, created_at

conversations
  id, owner_id -> users.id, document_id -> documents.id (nullable),
  title, created_at, updated_at

messages
  id, conversation_id -> conversations.id, role, content, position,
  citations, created_at
```

Document `status` values: `pending`, `processing`, `ready`, `failed`.
Message `role` values: `user`, `assistant`, `system`.

Deleting a user cascades to their documents and conversations. Deleting a
document cascades to its chunks and conversations. Deleting a conversation
cascades to its messages.

`documents.storage_path` is stored relative to the configured upload directory
and is not exposed to clients. `documents.checksum` is a SHA-256 hex digest
computed at upload time. Upload ownership is enforced per user: the owner is
the account behind the request's bearer token.

## Security notes

- Passwords are stored as bcrypt hashes with a per-password salt and are never
  returned by any endpoint. Login answers the same message for an unknown
  email and a wrong password, so accounts cannot be enumerated.
- Access tokens are signed JWTs. `JWT_SECRET_KEY` defaults to a development
  value; production deployments must set their own random secret of at least 32
  bytes, or anyone can forge a token for any user. Raising
  `ACCESS_TOKEN_EXPIRE_MINUTES` lengthens how long a stolen token stays valid.
- A token that names a deleted or disabled account is rejected with `401`.
- Every document, conversation, and insight query filters by `owner_id` from
  the token, so one account can never read another account's data.
- Upload and AI endpoints are rate limited per user (`429 rate_limited`) to
  bound abuse of the expensive paths.
- Document text is untrusted data and must never override system instructions.
- Retrieval must filter by `owner_id` before context is sent to an LLM.
- Provider keys are backend-only environment variables and are never returned
  to clients or committed to Git.
- File type validation must inspect content, not only the extension (Phase 2).
