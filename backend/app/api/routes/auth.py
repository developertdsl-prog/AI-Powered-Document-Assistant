"""Registration, login, and account identity."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import ErrorResponse
from app.services.auth import (
    authenticate_user,
    create_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses={
        409: {
            "model": ErrorResponse,
            "description": "An account with this email already exists.",
        },
    },
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    """Register a new user with an email and a password."""

    return register_user(db, request=request)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain a bearer token",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Incorrect email or password.",
        },
    },
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Exchange credentials for a JWT bearer token."""

    user = authenticate_user(db, request=request)

    return TokenResponse(
        access_token=create_access_token(user_id=user.id, settings=settings),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Describe the authenticated account",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Missing, invalid, or expired token.",
        },
    },
)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the account behind the request's bearer token."""

    return current_user
