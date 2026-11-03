"""Password hashing, JWT issuing, and account operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, EmailTakenError
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest

# bcrypt refuses longer inputs; the schema enforces the same limit so the
# error surfaces as a 422 instead of a 500.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password with a per-password salt."""

    return bcrypt.hashpw(
        password.encode("utf-8")[:BCRYPT_MAX_BYTES],
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plain password against its stored hash."""

    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:BCRYPT_MAX_BYTES],
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # A malformed stored hash is a failed verification, not a crash.
        return False


def create_access_token(*, user_id: uuid.UUID, settings: Settings) -> str:
    """Issue a signed JWT for the user."""

    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Validate a JWT and return the user id it names.

    Raises ``AuthenticationError`` for anything that is not a valid,
    unexpired token for this server.
    """

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthenticationError("The token is invalid or has expired.") from exc


def register_user(
    db: Session,
    *,
    request: RegisterRequest,
) -> User:
    """Create a new account, rejecting duplicate emails."""

    user = User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hash_password(request.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailTakenError() from exc

    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    *,
    request: LoginRequest,
) -> User:
    """Return the user when the credentials match, else raise 401.

    The same message covers unknown emails and wrong passwords so the
    endpoint cannot be used to enumerate registered addresses.
    """

    invalid = AuthenticationError("Incorrect email or password.")

    user = db.scalar(select(User).where(User.email == request.email))

    if user is None or not user.is_active:
        raise invalid

    if not verify_password(request.password, user.hashed_password or ""):
        raise invalid

    return user
