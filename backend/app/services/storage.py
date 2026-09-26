"""File-based storage for uploaded documents and assets with TTL support.

Layout::

    {data_dir}/
        documents/
            {doc_id}.pdf          # raw PDF bytes
            {doc_id}.json         # DocumentRecord metadata
        assets/
            {asset_id}.png        # asset image bytes
            {asset_id}.json       # AssetRecord metadata

All writes are atomic: content is first written to a ``.tmp`` sibling then
``os.replace``-ed to the final path.  File permissions are ``0o600``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.ids import new_asset_id, new_document_id

# ------------------------------------------------------------------
# Records
# ------------------------------------------------------------------


@dataclass
class DocumentRecord:
    """Persistent metadata for an uploaded document."""

    id: str
    filename: str
    size_bytes: int
    sha256: str
    page_count: int
    pdf_version: str | None
    pages: list[dict[str, Any]] = field(default_factory=list)
    has_signatures: bool = False
    signature_count: int = 0
    parent_id: str | None = None
    kind: str = "original"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "pdf_version": self.pdf_version,
            "pages": self.pages,
            "has_signatures": self.has_signatures,
            "signature_count": self.signature_count,
            "parent_id": self.parent_id,
            "kind": self.kind,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocumentRecord:
        return cls(**d)


@dataclass
class AssetRecord:
    """Persistent metadata for an uploaded asset."""

    id: str
    type: str  # image | text | drawn
    mime: str
    width_px: int
    height_px: int
    aspect_ratio: float
    sha256: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "mime": self.mime,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "aspect_ratio": self.aspect_ratio,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AssetRecord:
        return cls(**d)


# ------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------


class FileStorage:
    """Thread-safe file storage with atomic writes and TTL."""

    def __init__(self, data_dir: str | None = None) -> None:
        settings = get_settings()
        self._root = Path(data_dir or settings.data_dir)
        self._docs_dir = self._root / "documents"
        self._assets_dir = self._root / "assets"
        self._doc_ttl: float = settings.doc_ttl_minutes * 60.0
        self._docs_dir.mkdir(parents=True, exist_ok=True)
        self._assets_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Document operations
    # ------------------------------------------------------------------

    def store_document(
        self,
        content: bytes,
        filename: str,
        sha256: str,
        page_count: int,
        pdf_version: str | None = None,
        pages: list[dict[str, Any]] | None = None,
        has_signatures: bool = False,
        signature_count: int = 0,
        parent_id: str | None = None,
        kind: str = "original",
        ttl: float | None = None,
    ) -> DocumentRecord:
        """Atomically write a PDF and its metadata, return the record."""
        doc_id = new_document_id()
        now = time.time()
        expires = now + (ttl if ttl is not None else self._doc_ttl)

        record = DocumentRecord(
            id=doc_id,
            filename=filename,
            size_bytes=len(content),
            sha256=sha256,
            page_count=page_count,
            pdf_version=pdf_version,
            pages=pages or [],
            has_signatures=has_signatures,
            signature_count=signature_count,
            parent_id=parent_id,
            kind=kind,
            created_at=now,
            expires_at=expires,
        )

        pdf_path = self._doc_path(doc_id)
        meta_path = self._doc_meta_path(doc_id)

        _atomic_write(pdf_path, content)
        _atomic_write(meta_path, json.dumps(record.to_dict()).encode("utf-8"))

        return record

    def read_document(self, doc_id: str) -> tuple[DocumentRecord, bytes]:
        """Return (record, pdf_bytes) or raise DOCUMENT_NOT_FOUND."""
        record = self._load_doc_record(doc_id)
        pdf_path = self._doc_path(doc_id)
        if not pdf_path.exists():
            raise AppError(ErrorCode.DOCUMENT_NOT_FOUND)
        return record, pdf_path.read_bytes()

    def read_document_bytes(self, doc_id: str) -> bytes:
        """Return only the PDF bytes."""
        pdf_path = self._doc_path(doc_id)
        if not pdf_path.exists():
            raise AppError(ErrorCode.DOCUMENT_NOT_FOUND)
        return pdf_path.read_bytes()

    def read_document_record(self, doc_id: str) -> DocumentRecord:
        """Return only the metadata record."""
        return self._load_doc_record(doc_id)

    def delete_document(self, doc_id: str) -> None:
        """Mark a document as deleted and remove its files."""
        record = self._load_doc_record(doc_id)
        record.deleted = True
        _atomic_write(
            self._doc_meta_path(doc_id),
            json.dumps(record.to_dict()).encode("utf-8"),
        )
        pdf_path = self._doc_path(doc_id)
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)

    def list_expired_documents(self) -> list[DocumentRecord]:
        """Return all non-deleted documents past their TTL."""
        now = time.time()
        result: list[DocumentRecord] = []
        for meta_path in self._docs_dir.glob("*.json"):
            try:
                record = DocumentRecord.from_dict(json.loads(meta_path.read_text()))
                if not record.deleted and 0 < record.expires_at < now:
                    result.append(record)
            except Exception:  # noqa: S112
                continue
        return result

    # ------------------------------------------------------------------
    # Asset operations
    # ------------------------------------------------------------------

    def store_asset(
        self,
        content: bytes,
        asset_type: str,
        mime: str,
        width_px: int,
        height_px: int,
        sha256: str,
        ttl: float | None = None,
    ) -> AssetRecord:
        """Atomically write an asset image and its metadata."""
        asset_id = new_asset_id()
        now = time.time()
        expires = now + (ttl if ttl is not None else self._doc_ttl)

        record = AssetRecord(
            id=asset_id,
            type=asset_type,
            mime=mime,
            width_px=width_px,
            height_px=height_px,
            aspect_ratio=width_px / height_px if height_px > 0 else 1.0,
            sha256=sha256,
            created_at=now,
            expires_at=expires,
        )

        img_path = self._asset_path(asset_id)
        meta_path = self._asset_meta_path(asset_id)

        _atomic_write(img_path, content)
        _atomic_write(meta_path, json.dumps(record.to_dict()).encode("utf-8"))

        return record

    def read_asset(self, asset_id: str) -> tuple[AssetRecord, bytes]:
        """Return (record, image_bytes) or raise ASSET_NOT_FOUND."""
        record = self._load_asset_record(asset_id)
        img_path = self._asset_path(asset_id)
        if not img_path.exists():
            raise AppError(ErrorCode.ASSET_NOT_FOUND)
        return record, img_path.read_bytes()

    def read_asset_bytes(self, asset_id: str) -> bytes:
        """Return only the image bytes."""
        img_path = self._asset_path(asset_id)
        if not img_path.exists():
            raise AppError(ErrorCode.ASSET_NOT_FOUND)
        return img_path.read_bytes()

    def read_asset_record(self, asset_id: str) -> AssetRecord:
        """Return only the asset metadata record."""
        return self._load_asset_record(asset_id)

    def delete_asset(self, asset_id: str) -> None:
        """Mark an asset as deleted and remove its files."""
        record = self._load_asset_record(asset_id)
        record.deleted = True
        _atomic_write(
            self._asset_meta_path(asset_id),
            json.dumps(record.to_dict()).encode("utf-8"),
        )
        img_path = self._asset_path(asset_id)
        if img_path.exists():
            img_path.unlink(missing_ok=True)

    def list_expired_assets(self) -> list[AssetRecord]:
        """Return all non-deleted assets past their TTL."""
        now = time.time()
        result: list[AssetRecord] = []
        for meta_path in self._assets_dir.glob("*.json"):
            try:
                record = AssetRecord.from_dict(json.loads(meta_path.read_text()))
                if not record.deleted and 0 < record.expires_at < now:
                    result.append(record)
            except Exception:  # noqa: S112
                continue
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _doc_path(self, doc_id: str) -> Path:
        return self._docs_dir / f"{doc_id}.pdf"

    def _doc_meta_path(self, doc_id: str) -> Path:
        return self._docs_dir / f"{doc_id}.json"

    def _asset_path(self, asset_id: str) -> Path:
        return self._assets_dir / f"{asset_id}.png"

    def _asset_meta_path(self, asset_id: str) -> Path:
        return self._assets_dir / f"{asset_id}.json"

    def _load_doc_record(self, doc_id: str) -> DocumentRecord:
        meta_path = self._doc_meta_path(doc_id)
        if not meta_path.exists():
            raise AppError(ErrorCode.DOCUMENT_NOT_FOUND)
        try:
            record = DocumentRecord.from_dict(json.loads(meta_path.read_text()))
        except (json.JSONDecodeError, KeyError):
            raise AppError(ErrorCode.DOCUMENT_NOT_FOUND) from None
        if record.deleted:
            raise AppError(ErrorCode.DOCUMENT_NOT_FOUND)
        return record

    def _load_asset_record(self, asset_id: str) -> AssetRecord:
        meta_path = self._asset_meta_path(asset_id)
        if not meta_path.exists():
            raise AppError(ErrorCode.ASSET_NOT_FOUND)
        try:
            record = AssetRecord.from_dict(json.loads(meta_path.read_text()))
        except (json.JSONDecodeError, KeyError):
            raise AppError(ErrorCode.ASSET_NOT_FOUND) from None
        if record.deleted:
            raise AppError(ErrorCode.ASSET_NOT_FOUND)
        return record


# ------------------------------------------------------------------
# Atomic write helper
# ------------------------------------------------------------------


def _atomic_write(path: Path, content: bytes) -> None:
    """Write *content* to *path* atomically via a temporary sibling."""
    tmp = path.with_suffix(f".tmp.{uuid4().hex}")
    try:
        tmp.write_bytes(content)
        tmp.chmod(0o600)
        os.replace(str(tmp), str(path))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
