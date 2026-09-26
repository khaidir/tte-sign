"""Unit tests for FileStorage."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.storage import AssetRecord, DocumentRecord, FileStorage

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path: Path) -> FileStorage:
    """Create a FileStorage backed by a temp directory."""
    return FileStorage(data_dir=str(tmp_path))


# ------------------------------------------------------------------
# Document storage
# ------------------------------------------------------------------


class TestStoreDocument:
    def test_store_and_read(self, storage: FileStorage) -> None:
        record = storage.store_document(
            content=b"%PDF-1.4 test data",
            filename="test.pdf",
            sha256="abc123",
            page_count=1,
        )
        assert record.id.startswith("doc_")
        assert record.filename == "test.pdf"
        assert record.size_bytes == 18
        assert record.sha256 == "abc123"
        assert record.page_count == 1
        assert record.kind == "original"
        assert record.parent_id is None

        # Read back
        loaded, content = storage.read_document(record.id)
        assert loaded.id == record.id
        assert content == b"%PDF-1.4 test data"

    def test_store_with_metadata(self, storage: FileStorage) -> None:
        pages = [{"index": 0, "width_pt": 595.0, "height_pt": 842.0, "rotation": 0}]
        record = storage.store_document(
            content=b"%PDF-1.6 data",
            filename="report.pdf",
            sha256="def456",
            page_count=3,
            pdf_version="PDF 1.6",
            pages=pages,
            has_signatures=True,
            signature_count=2,
            parent_id="doc_parent123",
            kind="stamped",
        )
        assert record.pdf_version == "PDF 1.6"
        assert record.pages == pages
        assert record.has_signatures is True
        assert record.signature_count == 2
        assert record.parent_id == "doc_parent123"
        assert record.kind == "stamped"

    def test_store_with_custom_ttl(self, storage: FileStorage) -> None:
        record = storage.store_document(
            content=b"%PDF data",
            filename="short.pdf",
            sha256="xyz",
            page_count=1,
            ttl=1.0,
        )
        assert record.expires_at > time.time()
        assert record.expires_at < time.time() + 5

    def test_document_not_found(self, storage: FileStorage) -> None:
        with pytest.raises(AppError) as exc:
            storage.read_document("doc_nonexistent")
        assert exc.value.error_code == ErrorCode.DOCUMENT_NOT_FOUND

    def test_read_document_bytes(self, storage: FileStorage) -> None:
        storage.store_document(
            content=b"%PDF content",
            filename="f.pdf",
            sha256="h1",
            page_count=1,
        )
        # We need the id — store returns it
        record = storage.store_document(
            content=b"%PDF content2",
            filename="f2.pdf",
            sha256="h2",
            page_count=1,
        )
        content = storage.read_document_bytes(record.id)
        assert content == b"%PDF content2"

    def test_read_document_record(self, storage: FileStorage) -> None:
        record = storage.store_document(
            content=b"%PDF data",
            filename="meta.pdf",
            sha256="h3",
            page_count=2,
        )
        loaded = storage.read_document_record(record.id)
        assert loaded.id == record.id
        assert loaded.filename == "meta.pdf"

    def test_delete_document(self, storage: FileStorage) -> None:
        record = storage.store_document(
            content=b"%PDF to delete",
            filename="delete.pdf",
            sha256="h4",
            page_count=1,
        )
        storage.delete_document(record.id)
        with pytest.raises(AppError) as exc:
            storage.read_document(record.id)
        assert exc.value.error_code == ErrorCode.DOCUMENT_NOT_FOUND

    def test_delete_idempotent(self, storage: FileStorage) -> None:
        """Deleting a non-existent document should raise DOCUMENT_NOT_FOUND."""
        with pytest.raises(AppError) as exc:
            storage.delete_document("doc_nonexistent")
        assert exc.value.error_code == ErrorCode.DOCUMENT_NOT_FOUND

    def test_list_expired_documents(self, storage: FileStorage) -> None:
        # Store a document with a past TTL
        record = storage.store_document(
            content=b"%PDF expired",
            filename="expired.pdf",
            sha256="h5",
            page_count=1,
            ttl=-100,  # already expired
        )
        # Force expires_at to be in the past
        expired = storage.list_expired_documents()
        ids = [r.id for r in expired]
        assert record.id in ids

    def test_list_expired_documents_skips_fresh(self, storage: FileStorage) -> None:
        storage.store_document(
            content=b"%PDF fresh",
            filename="fresh.pdf",
            sha256="h6",
            page_count=1,
        )
        expired = storage.list_expired_documents()
        assert len(expired) == 0

    def test_atomic_write_survives_corrupt_meta(self, storage: FileStorage, tmp_path: Path) -> None:
        """A corrupt .json file should raise DOCUMENT_NOT_FOUND."""
        record = storage.store_document(
            content=b"%PDF data",
            filename="corrupt_meta.pdf",
            sha256="h7",
            page_count=1,
        )
        # Corrupt the metadata
        meta_path = tmp_path / "documents" / f"{record.id}.json"
        meta_path.write_text("{corrupt")
        with pytest.raises(AppError) as exc:
            storage.read_document(record.id)
        assert exc.value.error_code == ErrorCode.DOCUMENT_NOT_FOUND


# ------------------------------------------------------------------
# Asset storage
# ------------------------------------------------------------------


class TestStoreAsset:
    def test_store_and_read(self, storage: FileStorage) -> None:
        record = storage.store_asset(
            content=b"PNG data",
            asset_type="image",
            mime="image/png",
            width_px=100,
            height_px=50,
            sha256="img1",
        )
        assert record.id.startswith("ast_")
        assert record.type == "image"
        assert record.mime == "image/png"
        assert record.width_px == 100
        assert record.height_px == 50
        assert record.aspect_ratio == 2.0

        loaded, content = storage.read_asset(record.id)
        assert loaded.id == record.id
        assert content == b"PNG data"

    def test_asset_not_found(self, storage: FileStorage) -> None:
        with pytest.raises(AppError) as exc:
            storage.read_asset("ast_nonexistent")
        assert exc.value.error_code == ErrorCode.ASSET_NOT_FOUND

    def test_delete_asset(self, storage: FileStorage) -> None:
        record = storage.store_asset(
            content=b"PNG del",
            asset_type="image",
            mime="image/png",
            width_px=10,
            height_px=10,
            sha256="img2",
        )
        storage.delete_asset(record.id)
        with pytest.raises(AppError) as exc:
            storage.read_asset(record.id)
        assert exc.value.error_code == ErrorCode.ASSET_NOT_FOUND

    def test_list_expired_assets(self, storage: FileStorage) -> None:
        record = storage.store_asset(
            content=b"PNG expired",
            asset_type="image",
            mime="image/png",
            width_px=10,
            height_px=10,
            sha256="img3",
            ttl=-100,
        )
        expired = storage.list_expired_assets()
        ids = [r.id for r in expired]
        assert record.id in ids

    def test_list_expired_assets_skips_fresh(self, storage: FileStorage) -> None:
        storage.store_asset(
            content=b"PNG fresh",
            asset_type="image",
            mime="image/png",
            width_px=10,
            height_px=10,
            sha256="img4",
        )
        expired = storage.list_expired_assets()
        assert len(expired) == 0


# ------------------------------------------------------------------
# DocumentRecord / AssetRecord serialization
# ------------------------------------------------------------------


class TestRecordSerialization:
    def test_document_record_roundtrip(self) -> None:
        record = DocumentRecord(
            id="doc_test123",
            filename="test.pdf",
            size_bytes=100,
            sha256="abc",
            page_count=2,
            pdf_version="PDF 1.7",
            pages=[{"index": 0, "width_pt": 595.0, "height_pt": 842.0, "rotation": 0}],
            has_signatures=True,
            signature_count=1,
            parent_id="doc_parent",
            kind="stamped",
            created_at=1000.0,
            expires_at=2000.0,
        )
        d = record.to_dict()
        restored = DocumentRecord.from_dict(d)
        assert restored.id == record.id
        assert restored.filename == record.filename
        assert restored.size_bytes == record.size_bytes
        assert restored.sha256 == record.sha256
        assert restored.page_count == record.page_count
        assert restored.pdf_version == record.pdf_version
        assert restored.pages == record.pages
        assert restored.has_signatures == record.has_signatures
        assert restored.signature_count == record.signature_count
        assert restored.parent_id == record.parent_id
        assert restored.kind == record.kind
        assert restored.created_at == record.created_at
        assert restored.expires_at == record.expires_at

    def test_asset_record_roundtrip(self) -> None:
        record = AssetRecord(
            id="ast_test123",
            type="image",
            mime="image/png",
            width_px=200,
            height_px=100,
            aspect_ratio=2.0,
            sha256="img_hash",
            created_at=1000.0,
            expires_at=2000.0,
        )
        d = record.to_dict()
        restored = AssetRecord.from_dict(d)
        assert restored.id == record.id
        assert restored.type == record.type
        assert restored.mime == record.mime
        assert restored.width_px == record.width_px
        assert restored.height_px == record.height_px
        assert restored.aspect_ratio == record.aspect_ratio
        assert restored.sha256 == record.sha256
        assert restored.created_at == record.created_at
        assert restored.expires_at == record.expires_at
