"""Shared API dependencies."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.db.session import get_db
from app.models import User
from app.services.auth import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the user behind a JWT bearer token.

    Every protected endpoint depends on this. A missing, malformed, expired,
    or unknown token raises ``401 unauthorized`` in the standard error
    envelope.
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError(
            "Authentication required. Send an \"Authorization: Bearer <token>\" header."
        )

    user_id = decode_access_token(credentials.credentials, settings)
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise AuthenticationError(
            "The account in this token no longer exists or is disabled."
        )

    return user
