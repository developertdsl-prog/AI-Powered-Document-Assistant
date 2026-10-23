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
| Authentication | JWT bearer tokens, added in Phase 5 |
| Document ownership | Every document record has `owner_id`; enforcement arrives in Phase 5 |

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
| 401 | `unauthorized` | Missing or invalid credentials |
| 403 | `forbidden` | Authenticated but not allowed |
| 404 | `not_found` | Resource does not exist |
| 405 | `method_not_allowed` | Method not supported for this path |
| 409 | `conflict` | State conflict (for example a duplicate email) |
| 413 | `file_too_large` | Upload exceeds the configured limit (Phase 2) |
| 415 | `unsupported_media_type` | File type is not allowed (Phase 2) |
| 422 | `validation_error` | Request body or query validation failed |
| 429 | `rate_limited` | AI or upload rate limit exceeded (Phase 5) |
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

## Planned endpoints

These are contracts reserved for later phases and are **not implemented yet**.

| Phase | Method | Path | Purpose |
| --- | --- | --- | --- |
| 2 | `POST` | `/api/documents` | Upload a PDF, DOCX, or TXT file |
| 2 | `GET` | `/api/documents` | List the current user's documents |
| 2 | `GET` | `/api/documents/{id}` | Document details and processing status |
| 2 | `GET` | `/api/documents/{id}/text` | Extracted text with page metadata |
| 2 | `DELETE` | `/api/documents/{id}` | Delete a document |
| 4 | `POST` | `/api/documents/{id}/summaries` | Generate a summary |
| 4 | `POST` | `/api/documents/{id}/extractions` | Extract structured fields |
| 4 | `GET` | `/api/conversations` | List conversations |
| 4 | `POST` | `/api/conversations` | Create a conversation |
| 4 | `POST` | `/api/conversations/{id}/messages` | Ask a question and receive a cited answer |
| 5 | `POST` | `/api/auth/register` | Create an account |
| 5 | `POST` | `/api/auth/login` | Obtain an access token |

## Data model

```text
users
  id, email, full_name, hashed_password, is_active, created_at, updated_at

documents
  id, owner_id -> users.id, original_filename, storage_path, content_type,
  file_size_bytes, checksum, status, page_count, error_message,
  doc_metadata, processed_at, created_at, updated_at

document_chunks
  id, document_id -> documents.id, chunk_index, content, page_number,
  token_count, chunk_metadata, created_at

conversations
  id, owner_id -> users.id, document_id -> documents.id (nullable),
  title, created_at, updated_at

messages
  id, conversation_id -> conversations.id, role, content, citations, created_at
```

Document `status` values: `pending`, `processing`, `ready`, `failed`.
Message `role` values: `user`, `assistant`, `system`.

Deleting a user cascades to their documents and conversations. Deleting a
document cascades to its chunks and conversations. Deleting a conversation
cascades to its messages.

## Security notes

- Document text is untrusted data and must never override system instructions.
- Retrieval must filter by `owner_id` before context is sent to an LLM.
- Provider keys are backend-only environment variables and are never returned
  to clients or committed to Git.
- File type validation must inspect content, not only the extension (Phase 2).
