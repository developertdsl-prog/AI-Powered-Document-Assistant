"""Shared API dependencies."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User


def get_current_user(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the current user.

    Authentication is implemented in Phase 5. Until then, a single development
    user (configured with ``DEV_USER_EMAIL``) owns all uploads. This dependency
    is the only place that needs to change when real authentication lands.
    """

    email = settings.dev_user_email
    user = db.scalar(select(User).where(User.email == email))

    if user is not None:
        return user

    user = User(email=email, full_name=settings.dev_user_name)
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        # Another request created the development user concurrently.
        db.rollback()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise
    else:
        db.refresh(user)

    return user
