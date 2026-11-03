"""Tests for registration, login, bearer tokens, and rate limits."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import rate_limit as rate_limit_module
from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import check_rate_limit
from app.main import app
from app.models import Document, User


def register(
    client: TestClient,
    *,
    email: str = "ada@example.com",
    password: str = "correct-horse-battery",
    full_name: str | None = "Ada Lovelace",
):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


def login(
    client: TestClient,
    *,
    email: str = "ada@example.com",
    password: str = "correct-horse-battery",
):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- registration -----------------------------------------------------------


def test_register_creates_an_account_and_normalizes_the_email(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "  Ada@Example.COM ",
            "password": "correct-horse-battery",
            "full_name": "Ada Lovelace",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["full_name"] == "Ada Lovelace"
    assert "hashed_password" not in body
    assert "password" not in body

    stored = db_session.scalar(select(User).where(User.email == "ada@example.com"))
    assert stored is not None
    assert stored.hashed_password is not None
    assert stored.hashed_password != "correct-horse-battery"


def test_register_rejects_a_duplicate_email(
    auth_client: TestClient,
) -> None:
    register(auth_client)

    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "ada@example.com",
            "password": "another-pass-123",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_register_rejects_an_invalid_email(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "correct-horse-battery"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_register_rejects_a_short_password(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- login ------------------------------------------------------------------


def test_login_returns_a_bearer_token(
    auth_client: TestClient,
) -> None:
    register(auth_client)

    response = login(auth_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_login_rejects_wrong_password_and_unknown_email_alike(
    auth_client: TestClient,
) -> None:
    register(auth_client)

    wrong_password = login(auth_client, password="wrong-password-123")
    unknown_email = login(auth_client, email="nobody@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert (
        wrong_password.json()["error"]["message"]
        == unknown_email.json()["error"]["message"]
    )


# --- tokens -----------------------------------------------------------------


def test_me_returns_the_account_behind_the_token(
    auth_client: TestClient,
) -> None:
    register(auth_client)
    token = login(auth_client).json()["access_token"]

    response = auth_client.get("/api/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_protected_endpoints_reject_a_missing_token(
    auth_client: TestClient,
) -> None:
    response = auth_client.get("/api/documents")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_protected_endpoints_reject_a_malformed_token(
    auth_client: TestClient,
) -> None:
    response = auth_client.get(
        "/api/documents",
        headers=auth_header("not-a-token"),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_protected_endpoints_reject_a_token_from_another_secret(
    auth_client: TestClient,
    app_settings: Settings,
) -> None:
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "some-other-secret-at-least-32-bytes-long",
        algorithm=app_settings.jwt_algorithm,
    )

    response = auth_client.get("/api/documents", headers=auth_header(forged))

    assert response.status_code == 401


def test_protected_endpoints_reject_an_expired_token(
    auth_client: TestClient,
    db_session: Session,
    app_settings: Settings,
) -> None:
    register(auth_client)
    user = db_session.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None

    expired = jwt.encode(
        {
            "sub": str(user.id),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        app_settings.jwt_secret_key,
        algorithm=app_settings.jwt_algorithm,
    )

    response = auth_client.get("/api/documents", headers=auth_header(expired))

    assert response.status_code == 401


def test_me_rejects_a_token_whose_account_was_deleted(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    register(auth_client)
    token = login(auth_client).json()["access_token"]

    user = db_session.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None
    db_session.delete(user)
    db_session.commit()

    response = auth_client.get("/api/auth/me", headers=auth_header(token))

    assert response.status_code == 401


def test_documents_are_scoped_to_the_token_owner(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    register(auth_client, email="ada@example.com")
    ada_token = login(auth_client, email="ada@example.com").json()["access_token"]

    ada = db_session.scalar(select(User).where(User.email == "ada@example.com"))
    assert ada is not None
    db_session.add(
        Document(
            owner_id=ada.id,
            original_filename="ada-notes.txt",
            storage_path=f"{ada.id}/ada-notes.txt",
            content_type="text/plain",
            file_size_bytes=4,
            status="ready",
        )
    )
    db_session.commit()

    register(auth_client, email="grace@example.com")
    grace_token = login(auth_client, email="grace@example.com").json()["access_token"]

    ada_sees = auth_client.get(
        "/api/documents", headers=auth_header(ada_token)
    ).json()
    grace_sees = auth_client.get(
        "/api/documents", headers=auth_header(grace_token)
    ).json()

    assert ada_sees["total"] == 1
    assert grace_sees == {"items": [], "total": 0}


# --- rate limiting ----------------------------------------------------------


def test_ai_endpoints_return_429_after_the_limit(
    auth_client: TestClient,
    app_settings: Settings,
) -> None:
    limited = Settings(
        upload_dir=app_settings.upload_dir,
        jwt_secret_key=app_settings.jwt_secret_key,
        rate_limit_requests=2,
        rate_limit_window_seconds=60,
        process_uploads_in_background=False,
        embedding_provider="hash",
        llm_provider="extractive",
    )
    app.dependency_overrides[get_settings] = lambda: limited

    register(auth_client)
    token = login(auth_client).json()["access_token"]

    missing = uuid.uuid4()
    first = auth_client.post(
        f"/api/documents/{missing}/summaries",
        headers=auth_header(token),
        json={},
    )
    second = auth_client.post(
        f"/api/documents/{missing}/summaries",
        headers=auth_header(token),
        json={},
    )
    third = auth_client.post(
        f"/api/documents/{missing}/summaries",
        headers=auth_header(token),
        json={},
    )

    # The dependency runs before the handler, so the first two requests reach
    # the endpoint (404 for the missing document) and only the third is cut.
    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"


def test_upload_and_ai_limits_are_separate_buckets() -> None:
    limited = Settings(
        jwt_secret_key="x",
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    key = f"bucket-test-{uuid.uuid4()}"

    # One upload and one AI call are both fine at limit 1 because they draw
    # from different scopes; the second AI call trips the bucket.
    check_rate_limit(scope="upload", key=key, settings=limited)
    check_rate_limit(scope="ai", key=key, settings=limited)

    with pytest.raises(RateLimitExceededError):
        check_rate_limit(scope="ai", key=key, settings=limited)


def test_rate_limit_window_resets_after_it_elapses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        jwt_secret_key="x",
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    key = f"window-test-{uuid.uuid4()}"
    now = 1_000.0

    monkeypatch.setattr(rate_limit_module, "monotonic", lambda: now)

    check_rate_limit(scope="ai", key=key, settings=settings)

    with pytest.raises(RateLimitExceededError):
        check_rate_limit(scope="ai", key=key, settings=settings)

    now += 61

    check_rate_limit(scope="ai", key=key, settings=settings)


def test_disabled_rate_limit_never_blocks() -> None:
    settings = Settings(
        jwt_secret_key="x",
        rate_limit_enabled=False,
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    key = f"disabled-test-{uuid.uuid4()}"

    for _ in range(5):
        check_rate_limit(scope="ai", key=key, settings=settings)
