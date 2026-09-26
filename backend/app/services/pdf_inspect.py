"""PDF inspection — validation, page geometry, and signature detection.

All functions are designed to run in the worker pool (subprocess) so that
PyMuPDF and pyHanko never touch the event-loop thread.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

from app.core.errors import AppError, ErrorCode

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

PDF_MAGIC = b"%PDF"
MAX_PAGE_COUNT = 200


# ------------------------------------------------------------------
# Entry point for worker pool
# ------------------------------------------------------------------


def inspect_pdf(content: bytes) -> dict[str, Any]:
    """Validate *content* and return page geometry + signature info.

    Returns a dict suitable for ``DocumentRecord`` construction.
    Raises ``AppError`` for corrupt, encrypted, or oversized PDFs.
    """
    _validate_magic(content)

    try:
        import fitz  # type: ignore # PyMuPDF  # noqa: F811
    except ImportError:
        fitz = None  # type: ignore[assignment]

    if fitz is None:
        raise AppError(ErrorCode.INTERNAL_ERROR, "PyMuPDF not available in worker")

    doc = fitz.open(stream=content, filetype="pdf")  # type: ignore[arg-type]

    if doc.is_encrypted:  # type: ignore[union-attr]
        doc.close()
        raise AppError(ErrorCode.PDF_ENCRYPTED)

    page_count: int = doc.page_count  # type: ignore[union-attr]
    if page_count > MAX_PAGE_COUNT:
        doc.close()
        raise AppError(ErrorCode.TOO_MANY_PAGES)

    pdf_version: str | None = doc.metadata.get("format") if doc.metadata else None  # type: ignore[union-attr]

    pages: list[dict[str, Any]] = []
    for i in range(page_count): # pyright: ignore[reportUnknownArgumentType]
        page = doc[i]
        rotation: int = page.rotation or 0  # type: ignore[union-attr]
        # Normalize rotation
        rotation = rotation % 360 # type: ignore
        if rotation not in (0, 90, 180, 270):
            rotation = 0

        crop_box = page.cropbox  # type: ignore[union-attr]
        media_box = page.mediabox  # type: ignore[union-attr]

        pages.append(
            {
                "index": i,
                "width_pt": round(crop_box.width, 4),  # type: ignore[arg-type]
                "height_pt": round(crop_box.height, 4),  # type: ignore[arg-type]
                "rotation": rotation,
                "crop_box": [
                    round(crop_box.x0, 4),  # type: ignore[arg-type]
                    round(crop_box.y0, 4),  # type: ignore[arg-type]
                    round(crop_box.x1, 4),  # type: ignore[arg-type]
                    round(crop_box.y1, 4),  # type: ignore[arg-type]
                ],
                "media_box": [
                    round(media_box.x0, 4),  # type: ignore[arg-type]
                    round(media_box.y0, 4),  # type: ignore[arg-type]
                    round(media_box.x1, 4),  # type: ignore[arg-type]
                    round(media_box.y1, 4),  # type: ignore[arg-type]
                ],
            }
        )

    # Signature detection via pyHanko
    has_sigs = False
    sig_count = 0
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader

        reader = PdfFileReader(io.BytesIO(content))
        sigs = reader.embedded_signatures
        has_sigs = len(sigs) > 0
        sig_count = len(sigs)
    except Exception:  # noqa: S110
        pass  # best-effort signature detection

    doc.close()

    sha256 = hashlib.sha256(content).hexdigest()

    return {
        "sha256": sha256,
        "page_count": page_count,
        "pdf_version": pdf_version,
        "pages": pages,
        "has_signatures": has_sigs,
        "signature_count": sig_count,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _validate_magic(content: bytes) -> None:
    """Check PDF magic bytes; raise PDF_CORRUPT if missing."""
    if not content.startswith(PDF_MAGIC):
        raise AppError(ErrorCode.PDF_CORRUPT)
