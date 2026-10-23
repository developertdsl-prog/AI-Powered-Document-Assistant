"""File validation and local storage for document uploads."""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    EmptyFileError,
    FileTooLargeError,
    StorageError,
    UnsupportedFileTypeError,
)

logger = logging.getLogger(__name__)

READ_CHUNK_SIZE = 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ORIGINAL_FILENAME_LENGTH = 255


@dataclass(frozen=True)
class FileType:
    """Supported upload type metadata."""

    extension: str
    content_type: str


SUPPORTED_FILE_TYPES: dict[str, FileType] = {
    "pdf": FileType("pdf", "application/pdf"),
    "docx": FileType(
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "txt": FileType("txt", "text/plain"),
}


@dataclass(frozen=True)
class StoredFile:
    """Result of a successful upload write."""

    original_filename: str
    content_type: str
    file_size_bytes: int
    checksum: str
    relative_path: str


def normalize_filename(filename: str | None) -> str:
    """Return a safe display filename without any directory components."""

    raw = (filename or "").replace("\\", "/").strip()
    name = Path(raw).name

    if name in {"", ".", ".."}:
        raise EmptyFileError("A file name is required.")

    if len(name) > MAX_ORIGINAL_FILENAME_LENGTH:
        stem, dot, suffix = name.rpartition(".")
        if dot and len(suffix) <= 20:
            keep = MAX_ORIGINAL_FILENAME_LENGTH - len(suffix) - 1
            name = f"{stem[:keep]}.{suffix}"
        else:
            name = name[:MAX_ORIGINAL_FILENAME_LENGTH]

    return name


def _extension_of(filename: str) -> str:
    _, dot, suffix = filename.rpartition(".")
    if not dot or not suffix:
        raise UnsupportedFileTypeError(
            "The file must have a .pdf, .docx, or .txt extension."
        )
    return suffix.lower()


def _validate_extension(extension: str, settings: Settings) -> FileType:
    allowed = {item.lower().lstrip(".") for item in settings.allowed_file_types}
    file_type = SUPPORTED_FILE_TYPES.get(extension)

    if file_type is None or extension not in allowed:
        allowed_display = ", ".join(sorted(allowed)) or "none"
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{extension}'. Allowed types: {allowed_display}."
        )

    return file_type


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(1024)

    if not header.startswith(b"%PDF-"):
        raise UnsupportedFileTypeError(
            "The uploaded file is not a valid PDF document."
        )


def _validate_docx(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()

            if any(entry.flag_bits & 0x1 for entry in entries):
                raise UnsupportedFileTypeError(
                    "Password-protected DOCX files are not supported."
                )

            names = {entry.filename for entry in entries}
            if "word/document.xml" not in names:
                raise UnsupportedFileTypeError(
                    "The uploaded file is not a valid DOCX document."
                )

            uncompressed_size = sum(entry.file_size for entry in entries)
            if uncompressed_size > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise UnsupportedFileTypeError(
                    "The DOCX archive expands beyond the supported limit."
                )
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileTypeError(
            "The uploaded file is not a valid DOCX document."
        ) from exc


def _validate_txt(path: Path) -> None:
    with path.open("rb") as handle:
        sample = handle.read(8192)

    if b"\x00" in sample:
        raise UnsupportedFileTypeError(
            "The uploaded file does not look like a text document."
        )


def _validate_content(extension: str, path: Path) -> None:
    if extension == "pdf":
        _validate_pdf(path)
    elif extension == "docx":
        _validate_docx(path)
    else:
        _validate_txt(path)


def save_upload(
    file_obj: BinaryIO,
    filename: str | None,
    owner_id: uuid.UUID,
    settings: Settings,
) -> StoredFile:
    """Validate and persist an uploaded file under the owner's directory."""

    original_filename = normalize_filename(filename)
    extension = _extension_of(original_filename)
    file_type = _validate_extension(extension, settings)

    upload_root = Path(settings.upload_dir)
    owner_directory = upload_root / str(owner_id)
    owner_directory.mkdir(parents=True, exist_ok=True)

    storage_name = f"{uuid.uuid4().hex}.{file_type.extension}"
    final_path = owner_directory / storage_name
    temporary_path = owner_directory / f".{uuid.uuid4().hex}.part"

    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        try:
            file_obj.seek(0)
        except (AttributeError, OSError):
            pass

        with temporary_path.open("wb") as destination:
            while True:
                chunk = file_obj.read(READ_CHUNK_SIZE)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    raise FileTooLargeError(
                        "The uploaded file exceeds the "
                        f"{settings.max_upload_size_mb} MB limit."
                    )

                hasher.update(chunk)
                destination.write(chunk)

        if total_bytes == 0:
            raise EmptyFileError()

        _validate_content(extension, temporary_path)
        os.replace(temporary_path, final_path)
    except AppError:
        temporary_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        logger.exception("Failed to store upload %s", original_filename)
        raise StorageError() from exc
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return StoredFile(
        original_filename=original_filename,
        content_type=file_type.content_type,
        file_size_bytes=total_bytes,
        checksum=hasher.hexdigest(),
        relative_path=f"{owner_id}/{storage_name}",
    )


def delete_stored_file(relative_path: str, settings: Settings) -> None:
    """Delete a stored file, ignoring files that are already gone."""

    path = Path(settings.upload_dir) / relative_path

    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove stored file %s", path, exc_info=True)
