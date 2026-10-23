"""FastAPI exception handlers and the shared error envelope."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """Build a JSON error response using the public error envelope."""

    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the project-wide exception handlers to an application."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return error_response(exc.status_code, code, message)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            exc.status_code,
            exc.code,
            exc.message,
            exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            422,
            "validation_error",
            "Request validation failed.",
            exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error for %s %s", request.method, request.url)
        return error_response(
            500,
            "internal_error",
            "An unexpected error occurred.",
        )
