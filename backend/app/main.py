"""FastAPI application entry point."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import health
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for the AI-Powered Document Assistant. "
            "Document ingestion, retrieval, and chat are added in later phases."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])

    @app.get("/", include_in_schema=False)
    def read_root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "http_error"
        if exc.status_code == 404:
            code = "not_found"
        elif exc.status_code == 401:
            code = "unauthorized"
        elif exc.status_code == 403:
            code = "forbidden"

        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_response(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
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
        return _error_response(
            500,
            "internal_error",
            "An unexpected error occurred.",
        )

    return app


app = create_app()
