"""Domain exceptions mapped to the public API error envelope."""

from typing import Any


class AppError(Exception):
    """Base class for expected application errors."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class DocumentNotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Document not found.") -> None:
        super().__init__(message)


class ConversationNotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Conversation not found.") -> None:
        super().__init__(message)


class ConversationWithoutDocumentError(AppError):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str = (
            "This conversation is not linked to a document, "
            "so it cannot be answered."
        ),
    ) -> None:
        super().__init__(message)


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class EmptyFileError(AppError):
    status_code = 422
    code = "validation_error"

    def __init__(self, message: str = "The uploaded file is empty.") -> None:
        super().__init__(message)


class StorageError(AppError):
    status_code = 500
    code = "storage_error"

    def __init__(self, message: str = "The file could not be stored.") -> None:
        super().__init__(message)


class DocumentNotReadyError(AppError):
    status_code = 409
    code = "document_not_ready"

    def __init__(self, status: str) -> None:
        if status == "failed":
            message = (
                "Document processing failed. "
                "See the document details for the error."
            )
        else:
            message = (
                f"Document is not ready (status: {status}). "
                "Try again shortly."
            )
        super().__init__(message)


class EmbeddingsUnavailableError(AppError):
    status_code = 409
    code = "embeddings_unavailable"

    def __init__(
        self,
        message: str = (
            "Search is unavailable because embeddings are disabled "
            "on this server."
        ),
    ) -> None:
        super().__init__(message)


class AnswersUnavailableError(AppError):
    status_code = 409
    code = "answers_unavailable"

    def __init__(
        self,
        message: str = (
            "Answer generation is disabled on this server."
        ),
    ) -> None:
        super().__init__(message)


class AnswerProviderError(AppError):
    status_code = 503
    code = "service_unavailable"

    def __init__(
        self,
        message: str = (
            "The answer provider could not be reached. Try again shortly."
        ),
    ) -> None:
        super().__init__(message)


class InsightProviderError(AppError):
    status_code = 503
    code = "service_unavailable"

    def __init__(
        self,
        message: str = (
            "The summary provider could not be reached. Try again shortly."
        ),
    ) -> None:
        super().__init__(message)
