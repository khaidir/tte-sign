"""Error handling: AppError, ErrorCode catalog, and FastAPI exception handlers."""

from __future__ import annotations

import enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_request_id


class ErrorCode(enum.StrEnum):
    VALIDATION_ERROR = ("VALIDATION_ERROR", 400, "Validasi gagal")
    INVALID_FILE_TYPE = ("INVALID_FILE_TYPE", 400, "Jenis berkas tidak didukung")
    UNAUTHORIZED = ("UNAUTHORIZED", 401, "Tidak terautentikasi")
    FORBIDDEN = ("FORBIDDEN", 403, "Akses ditolak")
    SERVER_SIGNER_FORBIDDEN = (
        "SERVER_SIGNER_FORBIDDEN",
        403,
        "Segel organisasi tidak dapat digunakan",
    )
    DOCUMENT_NOT_FOUND = ("DOCUMENT_NOT_FOUND", 404, "Dokumen tidak ditemukan")
    ASSET_NOT_FOUND = ("ASSET_NOT_FOUND", 404, "Aset tidak ditemukan")
    EXISTING_SIGNATURES = (
        "EXISTING_SIGNATURES",
        409,
        "Dokumen sudah memiliki tanda tangan digital",
    )
    EXTRA_STAMPS_NOT_ALLOWED = ("EXTRA_STAMPS_NOT_ALLOWED", 409, "Stempel tambahan tidak diizinkan")
    DOCMDP_LOCKED = ("DOCMDP_LOCKED", 409, "Dokumen tersertifikasi tidak mengizinkan perubahan")
    FILE_TOO_LARGE = ("FILE_TOO_LARGE", 413, "Berkas terlalu besar")
    PDF_CORRUPT = ("PDF_CORRUPT", 422, "Berkas PDF rusak atau tidak dapat dibaca")
    PDF_ENCRYPTED = ("PDF_ENCRYPTED", 422, "Berkas PDF terenkripsi")
    TOO_MANY_PAGES = ("TOO_MANY_PAGES", 422, "Terlalu banyak halaman")
    IMAGE_INVALID = ("IMAGE_INVALID", 422, "Berkas gambar tidak valid")
    IMAGE_TOO_LARGE = ("IMAGE_TOO_LARGE", 422, "Gambar terlalu besar")
    UNSUPPORTED_CHARACTERS = ("UNSUPPORTED_CHARACTERS", 422, "Karakter tidak didukung font")
    INVALID_PAGE = ("INVALID_PAGE", 422, "Halaman tidak valid")
    PLACEMENT_OUT_OF_BOUNDS = ("PLACEMENT_OUT_OF_BOUNDS", 422, "Posisi di luar batas halaman")
    TOO_MANY_PLACEMENTS = ("TOO_MANY_PLACEMENTS", 422, "Terlalu banyak penempatan")
    PKCS12_INVALID = ("PKCS12_INVALID", 422, "Berkas PKCS#12 tidak valid")
    PKCS12_BAD_PASSPHRASE = ("PKCS12_BAD_PASSPHRASE", 422, "Passphrase PKCS#12 salah")
    CERT_EXPIRED = ("CERT_EXPIRED", 422, "Sertifikat telah kedaluwarsa")
    CERT_NOT_YET_VALID = ("CERT_NOT_YET_VALID", 422, "Sertifikat belum berlaku")
    CERT_KEY_USAGE = ("CERT_KEY_USAGE", 422, "Sertifikat tidak memiliki key usage yang sesuai")
    CERT_CHAIN_INCOMPLETE = ("CERT_CHAIN_INCOMPLETE", 422, "Rantai sertifikat tidak lengkap")
    CONSENT_REQUIRED = ("CONSENT_REQUIRED", 422, "Persetujuan wajib dicentang")
    LEVEL_NOT_ALLOWED = ("LEVEL_NOT_ALLOWED", 422, "Level PAdES tidak diizinkan")
    TSA_NOT_CONFIGURED = ("TSA_NOT_CONFIGURED", 422, "TSA belum dikonfigurasi")
    RATE_LIMITED = ("RATE_LIMITED", 429, "Terlalu banyak permintaan")
    TOO_MANY_ATTEMPTS = ("TOO_MANY_ATTEMPTS", 429, "Terlalu banyak percobaan")
    TSA_UNAVAILABLE = ("TSA_UNAVAILABLE", 502, "Layanan TSA tidak tersedia")
    REVOCATION_UNAVAILABLE = ("REVOCATION_UNAVAILABLE", 502, "Layanan OCSP/CRL tidak tersedia")
    BUSY = ("BUSY", 503, "Sistem sibuk, coba lagi")
    JOB_TIMEOUT = ("JOB_TIMEOUT", 504, "Pemrosesan melebihi batas waktu")
    INTERNAL_ERROR = ("INTERNAL_ERROR", 500, "Terjadi kesalahan internal")

    def __new__(cls, code: str, status: int, title: str) -> ErrorCode:
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.status = status
        obj.title = title
        return obj

    def __init__(self, code: str, status: int, title: str) -> None:
        self.code = code
        self.status = status
        self.title = title


class AppError(Exception):
    """Application-level error that maps to RFC 9457 Problem Details."""

    def __init__(
        self,
        error_code: ErrorCode,
        detail: str | None = None,
        extra: dict[str, Any] | None = None,
        instance: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.detail = detail or error_code.title
        self.extra = extra or {}
        self.instance = instance
        super().__init__(self.detail)

    def __str__(self) -> str:
        return self.detail

    def __reduce__(self) -> tuple:
        """Support pickling across process boundaries."""
        return (
            self.__class__,
            (self.error_code, self.detail, self.extra, self.instance),
        )


def _problem_response(
    status: int,
    title: str,
    code: str,
    detail: str,
    instance: str | None = None,
    request_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://tte-pdf/errors/{code.lower()}",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if request_id:
        body["request_id"] = request_id
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def _get_instance(request: Request) -> str:
    return str(request.url.path)


def _get_req_id(request: Request) -> str:
    try:
        return get_request_id()
    except LookupError:
        return request.headers.get("X-Request-ID", "")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _problem_response(
        status=exc.error_code.status,
        title=exc.error_code.title,
        code=exc.error_code.code,
        detail=exc.detail,
        instance=_get_instance(request),
        request_id=_get_req_id(request),
        extra=exc.extra,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors_list = []
    for err in exc.errors():
        loc = " → ".join(str(part) for part in err.get("loc", []))
        msg = err.get("msg", "")
        errors_list.append({"location": loc, "message": msg})
    return _problem_response(
        status=400,
        title=ErrorCode.VALIDATION_ERROR.title,
        code=ErrorCode.VALIDATION_ERROR.code,
        detail="Salah satu atau beberapa field tidak valid.",
        instance=_get_instance(request),
        request_id=_get_req_id(request),
        extra={"errors": errors_list},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        code = "NOT_FOUND"
        title = "Tidak ditemukan"
        detail = "Endpoint atau sumber daya tidak ditemukan."
    elif exc.status_code == 405:
        code = "METHOD_NOT_ALLOWED"
        title = "Metode tidak diizinkan"
        detail = f"Metode {request.method} tidak diizinkan untuk endpoint ini."
    else:
        code = f"HTTP_{exc.status_code}"
        title = "Kesalahan HTTP"
        detail = exc.detail or ""
    return _problem_response(
        status=exc.status_code,
        title=title,
        code=code,
        detail=detail,
        instance=_get_instance(request),
        request_id=_get_req_id(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging

    logger = logging.getLogger("tte.error")
    req_id = _get_req_id(request)
    logger.error(
        "Unhandled exception",
        exc_info=True,
        extra={"request_id": req_id, "path": str(request.url.path)},
    )
    return _problem_response(
        status=500,
        title=ErrorCode.INTERNAL_ERROR.title,
        code=ErrorCode.INTERNAL_ERROR.code,
        detail="Terjadi kesalahan internal. Silakan coba lagi atau hubungi dukungan.",
        instance=_get_instance(request),
        request_id=req_id,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
