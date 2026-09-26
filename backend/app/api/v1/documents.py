"""Document API endpoints — upload, metadata, download, delete."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.core.audit import AuditLogger
from app.core.errors import AppError, ErrorCode
from app.domain.schemas import DocumentMeta, PageInfo
from app.services.pdf_inspect import inspect_pdf
from app.services.storage import DocumentRecord, FileStorage
from app.services.worker_pool import WorkerPool

logger = logging.getLogger("tte.api.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


# ------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------


def _get_storage() -> FileStorage:
    """Dependency: return the application-wide FileStorage instance."""
    from app.main import app_state

    return app_state.storage


def _get_pool() -> WorkerPool:
    """Dependency: return the application-wide WorkerPool instance."""
    from app.main import app_state

    return app_state.pool


def _get_audit() -> AuditLogger:
    """Dependency: return the application-wide AuditLogger instance."""
    from app.main import app_state

    return app_state.audit


# ------------------------------------------------------------------
# POST /documents — Upload
# ------------------------------------------------------------------


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    storage: FileStorage = Depends(_get_storage),  # noqa: B008
    pool: WorkerPool = Depends(_get_pool),  # noqa: B008
    audit: AuditLogger = Depends(_get_audit),  # noqa: B008
    content_length: int | None = Header(None),  # noqa: B008
) -> DocumentMeta:
    """Upload a PDF document for signing or stamping.

    The file is validated (magic bytes, encryption, page count) in a worker
    process before being stored.
    """
    settings = get_settings()

    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError(ErrorCode.INVALID_FILE_TYPE)

    # Read content
    raw = await file.read()

    if not raw:
        raise AppError(ErrorCode.INVALID_FILE_TYPE)

    # Size check
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise AppError(ErrorCode.FILE_TOO_LARGE)

    # Inspect in worker pool
    try:
        info = await pool.run(inspect_pdf, raw)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("PDF inspection failed")
        raise AppError(ErrorCode.PDF_CORRUPT) from exc

    # Store
    record = storage.store_document(
        content=raw,
        filename=file.filename,
        sha256=info["sha256"],
        page_count=info["page_count"],
        pdf_version=info["pdf_version"],
        pages=info["pages"],
        has_signatures=info["has_signatures"],
        signature_count=info["signature_count"],
    )

    audit.emit(
        "document.uploaded",
        doc_id=record.id,
        filename=record.filename,
        size_bytes=record.size_bytes,
        page_count=record.page_count,
    )

    logger.info(
        "Document uploaded",
        extra={
            "doc_id": record.id,
            "filename": record.filename,
            "pages": record.page_count,
        },
    )

    return _record_to_meta(record)


# ------------------------------------------------------------------
# GET /documents/{id} — Metadata
# ------------------------------------------------------------------


@router.get("/{doc_id}")
async def get_document_metadata(
    doc_id: str,
    storage: FileStorage = Depends(_get_storage),  # noqa: B008
) -> DocumentMeta:
    """Return document metadata without the PDF content."""
    record = storage.read_document_record(doc_id)
    return _record_to_meta(record)


# ------------------------------------------------------------------
# GET /documents/{id}/file — Raw PDF download
# ------------------------------------------------------------------


@router.get("/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    storage: FileStorage = Depends(_get_storage),  # noqa: B008
    audit: AuditLogger = Depends(_get_audit),  # noqa: B008
    download: bool = Query(False, description="Trigger delete-after-download"),  # noqa: B008
) -> Response:
    """Return the raw PDF bytes.

    If ``download=true`` and ``TTE_DELETE_AFTER_DOWNLOAD`` is enabled, the
    document is scheduled for deletion after the response is sent.
    """
    record, pdf_bytes = storage.read_document(doc_id)

    audit.emit(
        "document.downloaded",
        doc_id=doc_id,
        filename=record.filename,
        download=download,
    )

    if download:
        settings = get_settings()
        if settings.delete_after_download:
            _schedule_deletion(doc_id, storage, audit)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{record.filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ------------------------------------------------------------------
# GET /documents/{id}/download — Force-download
# ------------------------------------------------------------------


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    storage: FileStorage = Depends(_get_storage),  # noqa: B008
    audit: AuditLogger = Depends(_get_audit),  # noqa: B008
) -> Response:
    """Force-download the PDF as an attachment.

    If ``TTE_DELETE_AFTER_DOWNLOAD`` is enabled, the document is scheduled
    for deletion after the response is sent.
    """
    record, pdf_bytes = storage.read_document(doc_id)

    audit.emit(
        "document.downloaded",
        doc_id=doc_id,
        filename=record.filename,
        download=True,
    )

    settings = get_settings()
    if settings.delete_after_download:
        _schedule_deletion(doc_id, storage, audit)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{record.filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ------------------------------------------------------------------
# DELETE /documents/{id}
# ------------------------------------------------------------------


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    storage: FileStorage = Depends(_get_storage),  # noqa: B008
    audit: AuditLogger = Depends(_get_audit),  # noqa: B008
) -> None:
    """Delete a document and its metadata."""
    record = storage.read_document_record(doc_id)
    storage.delete_document(doc_id)

    audit.emit(
        "document.deleted",
        doc_id=doc_id,
        filename=record.filename,
    )

    logger.info(
        "Document deleted",
        extra={"doc_id": doc_id, "filename": record.filename},
    )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _record_to_meta(record: DocumentRecord) -> DocumentMeta:
    """Convert a ``DocumentRecord`` to a ``DocumentMeta`` response."""
    pages = [
        PageInfo(
            index=p["index"],
            width_pt=p["width_pt"],
            height_pt=p["height_pt"],
            rotation=p["rotation"],
            crop_box=p["crop_box"],
            media_box=p["media_box"],
        )
        for p in record.pages
    ]

    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created_at))
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.expires_at))

    return DocumentMeta(
        id=record.id,
        parent_id=record.parent_id,
        kind=record.kind,  # type: ignore[arg-type]
        filename=record.filename,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
        page_count=record.page_count,
        pdf_version=record.pdf_version,
        pages=pages,
        has_signatures=record.has_signatures,
        signature_count=record.signature_count,
        created_at=created,
        expires_at=expires,
        links={
            "self": f"/api/v1/documents/{record.id}",
            "file": f"/api/v1/documents/{record.id}/file",
            "download": f"/api/v1/documents/{record.id}/download",
        },
    )


def _schedule_deletion(
    doc_id: str, storage: FileStorage, audit: AuditLogger
) -> None:
    """Schedule a document for deletion after download."""
    import asyncio

    async def _delayed_delete() -> None:
        await asyncio.sleep(5)
        try:
            storage.delete_document(doc_id)
            audit.emit(
                "document.deleted",
                doc_id=doc_id,
                reason="delete-after-download",
            )
        except AppError:
            pass  # already deleted

    asyncio.ensure_future(_delayed_delete())
