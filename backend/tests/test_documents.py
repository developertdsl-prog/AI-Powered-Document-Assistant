"""Tests for document upload, validation, storage, and ownership."""

import hashlib
import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings
from app.models import Document, User

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def make_docx_bytes() -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello</w:t>'
                "</w:r></w:p></w:body></w:document>"
            ),
        )

    return buffer.getvalue()


def upload(
    client: TestClient,
    *,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
):
    return client.post(
        "/api/documents",
        files={"file": (filename, content, content_type)},
    )


def test_upload_pdf_creates_document_and_stores_file(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
) -> None:
    response = upload(
        client,
        filename="Quarterly Report.pdf",
        content=PDF_BYTES,
        content_type="application/pdf",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "Quarterly Report.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["file_size_bytes"] == len(PDF_BYTES)
    assert body["status"] == "pending"
    assert body["checksum"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert body["page_count"] is None

    document = db_session.scalars(select(Document)).one()
    assert str(document.id) == body["id"]
    assert document.owner_id == user.id

    stored_path = Path(app_settings.upload_dir) / document.storage_path
    assert stored_path.is_file()
    assert stored_path.read_bytes() == PDF_BYTES


def test_upload_docx_is_accepted(client: TestClient) -> None:
    response = upload(
        client,
        filename="Requirements.docx",
        content=make_docx_bytes(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )

    assert response.status_code == 201
    assert response.json()["content_type"].endswith(
        "wordprocessingml.document"
    )


def test_upload_txt_is_accepted(client: TestClient) -> None:
    response = upload(
        client,
        filename="notes.txt",
        content=b"Line one\nLine two\n",
        content_type="text/plain",
    )

    assert response.status_code == 201
    assert response.json()["content_type"] == "text/plain"


def test_unsupported_extension_is_rejected(client: TestClient) -> None:
    response = upload(client, filename="malware.exe", content=PDF_BYTES)

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "unsupported_media_type"
    assert ".exe" in body["error"]["message"]


def test_fake_pdf_is_rejected(client: TestClient) -> None:
    response = upload(client, filename="fake.pdf", content=b"not a real pdf")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_pdf_extension_with_docx_content_is_rejected(
    client: TestClient,
) -> None:
    response = upload(client, filename="wrong.pdf", content=make_docx_bytes())

    assert response.status_code == 415


def test_empty_file_is_rejected(client: TestClient) -> None:
    response = upload(client, filename="empty.txt", content=b"")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_file_over_size_limit_is_rejected(client: TestClient) -> None:
    payload = b"%PDF-" + b"x" * (1024 * 1024)

    response = upload(client, filename="large.pdf", content=payload)

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "file_too_large"
    assert "1 MB" in body["error"]["message"]


def test_filename_path_traversal_is_sanitized(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
) -> None:
    response = upload(
        client,
        filename="..\\..\\evil.pdf",
        content=PDF_BYTES,
        content_type="application/pdf",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "evil.pdf"

    document = db_session.scalars(select(Document)).one()
    assert document.storage_path.startswith(f"{user.id}/")

    upload_root = Path(app_settings.upload_dir).resolve()
    stored_path = (upload_root / document.storage_path).resolve()
    assert stored_path.is_relative_to(upload_root)


def test_list_returns_only_current_users_documents(
    client: TestClient,
    db_session: Session,
    user: User,
) -> None:
    upload_response = upload(
        client,
        filename="mine.pdf",
        content=PDF_BYTES,
        content_type="application/pdf",
    )
    assert upload_response.status_code == 201

    other_user = User(email="other@example.com")
    db_session.add(other_user)
    db_session.flush()
    db_session.add(
        Document(
            owner_id=other_user.id,
            original_filename="theirs.pdf",
            storage_path=f"{other_user.id}/theirs.pdf",
            content_type="application/pdf",
            file_size_bytes=10,
            status="ready",
        )
    )
    db_session.commit()

    response = client.get("/api/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["original_filename"] for item in body["items"]] == [
        "mine.pdf"
    ]
    assert body["items"][0]["id"] == upload_response.json()["id"]


def test_other_users_document_detail_is_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(email="hidden@example.com")
    db_session.add(other_user)
    db_session.flush()
    document = Document(
        owner_id=other_user.id,
        original_filename="hidden.pdf",
        storage_path=f"{other_user.id}/hidden.pdf",
        content_type="application/pdf",
        file_size_bytes=10,
        status="ready",
    )
    db_session.add(document)
    db_session.commit()

    response = client.get(f"/api/documents/{document.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_document_id_returns_validation_error(
    client: TestClient,
) -> None:
    response = client.get("/api/documents/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_paginates_documents(
    client: TestClient,
    db_session: Session,
    user: User,
) -> None:
    for index in range(3):
        db_session.add(
            Document(
                owner_id=user.id,
                original_filename=f"doc-{index}.txt",
                storage_path=f"{user.id}/doc-{index}.txt",
                content_type="text/plain",
                file_size_bytes=4,
                status="ready",
            )
        )
    db_session.commit()

    response = client.get("/api/documents", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_development_user_is_created_once(db_session: Session) -> None:
    settings = Settings(
        dev_user_email="solo@example.com",
        dev_user_name="Solo Tester",
    )

    first = get_current_user(db_session, settings)
    second = get_current_user(db_session, settings)

    assert first.id == second.id
    assert first.email == "solo@example.com"
