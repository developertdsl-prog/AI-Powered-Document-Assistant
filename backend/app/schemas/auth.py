"""Schemas for registration, login, and token responses."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# bcrypt processes at most 72 bytes per password; longer inputs are rejected
# instead of silently truncated so two different passwords can never collide.
MAX_PASSWORD_LENGTH = 72


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()

        if not EMAIL_PATTERN.match(cleaned):
            raise ValueError("Enter a valid email address.")

        return cleaned


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
