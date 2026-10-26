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
| Document ownership | Every document record has `owner_id`; document and page queries are scoped to the current owner. JWT authentication arrives in Phase 5. |

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
| 409 | `document_not_ready` | Extracted text was requested before processing finished |
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

Until Phase 5 authentication, uploads are owned by the development user
(`DEV_USER_EMAIL` / `DEV_USER_NAME`).

### `GET /api/documents`

List documents owned by the current user.

**Query parameters:**

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `limit` | integer | `50` | `1` to `100` |
| `offset` | integer | `0` | `>= 0` |

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

## Planned endpoints

These are contracts reserved for later phases and are **not implemented yet**.

| Phase | Method | Path | Purpose |
| --- | --- | --- | --- |
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
  id, conversation_id -> conversations.id, role, content, citations, created_at
```

Document `status` values: `pending`, `processing`, `ready`, `failed`.
Message `role` values: `user`, `assistant`, `system`.

Deleting a user cascades to their documents and conversations. Deleting a
document cascades to its chunks and conversations. Deleting a conversation
cascades to its messages.

`documents.storage_path` is stored relative to the configured upload directory
and is not exposed to clients. `documents.checksum` is a SHA-256 hex digest
computed at upload time. Upload ownership is enforced per user (currently the
development user until Phase 5 authentication).

## Security notes

- Document text is untrusted data and must never override system instructions.
- Retrieval must filter by `owner_id` before context is sent to an LLM.
- Provider keys are backend-only environment variables and are never returned
  to clients or committed to Git.
- File type validation must inspect content, not only the extension (Phase 2).
