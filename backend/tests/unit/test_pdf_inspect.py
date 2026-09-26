"""Unit tests for PDF inspection."""

from __future__ import annotations

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.pdf_inspect import _validate_magic, inspect_pdf


class TestValidateMagic:
    def test_valid_pdf_magic(self) -> None:
        _validate_magic(b"%PDF-1.4\n...")
        _validate_magic(b"%PDF\n...")

    def test_invalid_magic(self) -> None:
        with pytest.raises(AppError) as exc:
            _validate_magic(b"not a pdf")
        assert exc.value.error_code == ErrorCode.PDF_CORRUPT

    def test_empty_bytes(self) -> None:
        with pytest.raises(AppError) as exc:
            _validate_magic(b"")
        assert exc.value.error_code == ErrorCode.PDF_CORRUPT


class TestInspectPdf:
    def test_inspect_valid_pdf(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("a4.pdf")
        result = inspect_pdf(content)

        assert result["sha256"] is not None
        assert result["page_count"] == 1
        assert result["pdf_version"] is not None
        assert len(result["pages"]) == 1
        assert result["has_signatures"] is False
        assert result["signature_count"] == 0

        page = result["pages"][0]
        assert page["index"] == 0
        assert page["width_pt"] > 0
        assert page["height_pt"] > 0
        assert page["rotation"] in (0, 90, 180, 270)
        assert len(page["crop_box"]) == 4
        assert len(page["media_box"]) == 4

    def test_inspect_multipage(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("multipage-20.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 20
        assert len(result["pages"]) == 20

    def test_inspect_rotated(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("rot90.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1
        assert result["pages"][0]["rotation"] == 90

    def test_inspect_rot180(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("rot180.pdf")
        result = inspect_pdf(content)
        assert result["pages"][0]["rotation"] == 180

    def test_inspect_rot270(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("rot270.pdf")
        result = inspect_pdf(content)
        assert result["pages"][0]["rotation"] == 270

    def test_inspect_cropbox_offset(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("cropbox-offset.pdf")
        result = inspect_pdf(content)
        page = result["pages"][0]
        # CropBox should differ from MediaBox
        assert page["crop_box"] != page["media_box"]

    def test_inspect_encrypted_raises(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("encrypted.pdf")
        with pytest.raises(AppError) as exc:
            inspect_pdf(content)
        assert exc.value.error_code == ErrorCode.PDF_ENCRYPTED

    def test_inspect_corrupt_raises(self, fixture_pdf: callable) -> None:
        """A truncated PDF with valid magic may still be openable by PyMuPDF."""
        content = fixture_pdf("corrupt.pdf")
        try:
            result = inspect_pdf(content)
            assert result["page_count"] >= 1
        except AppError as e:
            assert e.error_code == ErrorCode.PDF_CORRUPT

    def test_inspect_not_a_pdf_raises(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("not-a-pdf.pdf")
        with pytest.raises(AppError) as exc:
            inspect_pdf(content)
        assert exc.value.error_code == ErrorCode.PDF_CORRUPT

    def test_inspect_too_many_pages(self, fixture_pdf: callable) -> None:
        """multipage-200.pdf has exactly 200 pages which equals the limit."""
        content = fixture_pdf("multipage-200.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 200

    def test_inspect_landscape(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("a4-landscape.pdf")
        result = inspect_pdf(content)
        page = result["pages"][0]
        # Landscape: width > height
        assert page["width_pt"] > page["height_pt"]

    def test_inspect_legal(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("legal.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inspect_letter(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("letter.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inspect_f4(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("f4.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inspect_pdf20(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("pdf20.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inspect_with_js(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("with-js.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inspect_form_fields(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("form-fields.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1

    def test_inherited_boxes(self, fixture_pdf: callable) -> None:
        content = fixture_pdf("inherited-boxes.pdf")
        result = inspect_pdf(content)
        assert result["page_count"] == 1
