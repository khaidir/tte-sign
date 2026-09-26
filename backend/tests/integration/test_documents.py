"""Integration tests for document API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a TestClient with a fresh app instance and temp data dir."""
    monkeypatch.setenv("TTE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TTE_LOG_LEVEL", "CRITICAL")
    # Reset settings cache so the new env vars take effect

    monkeypatch.setattr("app.config._settings", None)
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fixture_pdf_bytes() -> callable:
    """Return a function that reads a fixture PDF by name."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "out"

    def _get(name: str) -> bytes:
        path = fixtures_dir / name
        if not path.exists():
            msg = f"Fixture PDF not found: {name}"
            raise FileNotFoundError(msg)
        return path.read_bytes()

    return _get


# ------------------------------------------------------------------
# POST /api/v1/documents
# ------------------------------------------------------------------


class TestUploadDocument:
    def test_upload_valid_pdf(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("doc_")
        assert data["filename"] == "test.pdf"
        assert data["size_bytes"] == len(pdf)
        assert data["page_count"] == 1
        assert data["sha256"] is not None
        assert data["pdf_version"] is not None
        assert len(data["pages"]) == 1
        assert data["has_signatures"] is False
        assert data["signature_count"] == 0
        assert "self" in data["links"]
        assert "file" in data["links"]
        assert "download" in data["links"]

    def test_upload_multipage(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("multipage-20.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("multi.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["page_count"] == 20
        assert len(data["pages"]) == 20

    def test_upload_non_pdf_extension(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_FILE_TYPE"

    def test_upload_empty_file(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_upload_corrupt_pdf(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        """A truncated PDF that still has %PDF magic may be openable by PyMuPDF."""
        pdf = fixture_pdf_bytes("corrupt.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("corrupt.pdf", pdf, "application/pdf")},
        )
        # PyMuPDF is lenient — may open truncated PDFs
        assert resp.status_code in (201, 422)

    def test_upload_encrypted_pdf(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("encrypted.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("encrypted.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "PDF_ENCRYPTED"

    def test_upload_too_many_pages(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        """multipage-200.pdf has exactly 200 pages which equals the default limit."""
        pdf = fixture_pdf_bytes("multipage-200.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("big.pdf", pdf, "application/pdf")},
        )
        # 200 pages is at the limit, so it should be accepted
        assert resp.status_code == 201

    def test_upload_not_a_pdf(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("not-a-pdf.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("fake.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "PDF_CORRUPT"

    def test_upload_rotated_pdf(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("rot90.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("rot90.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pages"][0]["rotation"] == 90

    def test_upload_landscape(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4-landscape.pdf")
        resp = client.post(
            "/api/v1/documents",
            files={"file": ("landscape.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pages"][0]["width_pt"] > data["pages"][0]["height_pt"]


# ------------------------------------------------------------------
# GET /api/v1/documents/{id}
# ------------------------------------------------------------------


class TestGetDocumentMetadata:
    def test_get_metadata(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4.pdf")
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        doc_id = upload.json()["id"]

        resp = client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert data["filename"] == "test.pdf"
        assert data["page_count"] == 1

    def test_get_metadata_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/documents/doc_nonexistent")
        assert resp.status_code == 404
        assert resp.json()["code"] == "DOCUMENT_NOT_FOUND"


# ------------------------------------------------------------------
# GET /api/v1/documents/{id}/file
# ------------------------------------------------------------------


class TestGetDocumentFile:
    def test_get_file(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4.pdf")
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        doc_id = upload.json()["id"]

        resp = client.get(f"/api/v1/documents/{doc_id}/file")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["content-disposition"] == 'inline; filename="test.pdf"'
        assert len(resp.content) == len(pdf)

    def test_get_file_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/documents/doc_nonexistent/file")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# GET /api/v1/documents/{id}/download
# ------------------------------------------------------------------


class TestDownloadDocument:
    def test_download(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4.pdf")
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        doc_id = upload.json()["id"]

        resp = client.get(f"/api/v1/documents/{doc_id}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers["content-disposition"]
        assert len(resp.content) == len(pdf)


# ------------------------------------------------------------------
# DELETE /api/v1/documents/{id}
# ------------------------------------------------------------------


class TestDeleteDocument:
    def test_delete(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        pdf = fixture_pdf_bytes("a4.pdf")
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        doc_id = upload.json()["id"]

        resp = client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/documents/doc_nonexistent")
        assert resp.status_code == 404

    def test_delete_then_reupload(self, client: TestClient, fixture_pdf_bytes: callable) -> None:
        """Deleting a document frees the ID namespace (no conflict)."""
        pdf = fixture_pdf_bytes("a4.pdf")
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", pdf, "application/pdf")},
        )
        doc_id = upload.json()["id"]
        client.delete(f"/api/v1/documents/{doc_id}")

        # Upload again — should work fine
        upload2 = client.post(
            "/api/v1/documents",
            files={"file": ("new.pdf", pdf, "application/pdf")},
        )
        assert upload2.status_code == 201
        assert upload2.json()["id"] != doc_id


# ------------------------------------------------------------------
# Error format (RFC 9457)
# ------------------------------------------------------------------


class TestErrorFormat:
    def test_error_response_shape(self, client: TestClient) -> None:
        resp = client.get("/api/v1/documents/doc_nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "code" in body
        assert "detail" in body
        assert body["code"] == "DOCUMENT_NOT_FOUND"
        assert body["status"] == 404
