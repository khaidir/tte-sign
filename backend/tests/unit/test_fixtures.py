"""Unit tests for PDF fixture properties.

Verifies that each generated fixture has the expected properties
as specified in the PRD Appendix D test matrix.
"""

from __future__ import annotations

import pytest
from PIL import Image

from tests.conftest import ASSETS_DIR, FIXTURES_OUT_DIR

# Skip all tests if fixtures haven't been generated
pytestmark = pytest.mark.skipif(
    not FIXTURES_OUT_DIR.exists(),
    reason="Fixtures not generated (run 'make fixtures' first)",
)


def _open_pdf(name: str):
    """Open a PDF fixture and return the document."""
    import fitz  # noqa: N812
    path = FIXTURES_OUT_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture not found: {name}")
    return fitz.open(str(path))


class TestStandardPages:
    """Test standard page size PDFs."""

    @pytest.mark.parametrize("name,w,h", [
        ("a4.pdf", 595, 842),
        ("letter.pdf", 612, 792),
        ("legal.pdf", 612, 1008),
        ("f4.pdf", 595, 935),
        ("a4-landscape.pdf", 842, 595),
    ])
    def test_page_size(self, name, w, h):
        doc = _open_pdf(name)
        assert len(doc) == 1, f"{name}: expected 1 page"
        page = doc[0]
        assert page.rect.width == w, f"{name}: expected width {w}, got {page.rect.width}"
        assert page.rect.height == h, f"{name}: expected height {h}, got {page.rect.height}"
        doc.close()

    def test_corner_labels_present(self):
        """Verify that corner labels are present (text on page)."""
        doc = _open_pdf("a4.pdf")
        page = doc[0]
        text = page.get_text()
        assert "top-left" in text
        assert "top-right" in text
        assert "bottom-left" in text
        assert "bottom-right" in text
        doc.close()


class TestRotatedPages:
    """Test PDFs with /Rotate."""

    @pytest.mark.parametrize("name,rotation", [
        ("rot90.pdf", 90),
        ("rot180.pdf", 180),
        ("rot270.pdf", 270),
    ])
    def test_rotation(self, name, rotation):
        doc = _open_pdf(name)
        assert len(doc) == 1
        page = doc[0]
        assert page.rotation == rotation, (
            f"{name}: expected rotation {rotation}, got {page.rotation}"
        )
        doc.close()


class TestCropBox:
    """Test PDFs with CropBox offset."""

    def test_cropbox_offset(self):
        doc = _open_pdf("cropbox-offset.pdf")
        page = doc[0]
        cropbox = page.cropbox
        assert cropbox.x0 == 50, f"cropbox.x0: expected 50, got {cropbox.x0}"
        assert cropbox.y0 == 60, f"cropbox.y0: expected 60, got {cropbox.y0}"
        assert cropbox.x1 == 545, f"cropbox.x1: expected 545, got {cropbox.x1}"
        assert cropbox.y1 == 780, f"cropbox.y1: expected 780, got {cropbox.y1}"
        doc.close()

    def test_cropbox_offset_rot90(self):
        doc = _open_pdf("cropbox-offset-rot90.pdf")
        page = doc[0]
        assert page.rotation == 90
        cropbox = page.cropbox
        assert cropbox.x0 == 50
        assert cropbox.y0 == 60
        assert cropbox.x1 == 545
        assert cropbox.y1 == 780
        doc.close()


class TestMultipage:
    """Test multi-page PDFs."""

    @pytest.mark.parametrize("name,count", [
        ("multipage-20.pdf", 20),
        ("multipage-200.pdf", 200),
    ])
    def test_page_count(self, name, count):
        doc = _open_pdf(name)
        assert len(doc) == count, f"{name}: expected {count} pages, got {len(doc)}"
        doc.close()


class TestSpecialPDFs:
    """Test special PDF fixtures."""

    def test_encrypted(self):
        """Encrypted PDF should require a password to open."""
        doc = _open_pdf("encrypted.pdf")
        assert doc.is_encrypted, "encrypted.pdf should be encrypted"
        assert doc.authenticate("rahasia123"), "Should authenticate with user password"
        doc.close()

    def test_corrupt(self):
        """Corrupt PDF should fail to open or have issues."""
        path = FIXTURES_OUT_DIR / "corrupt.pdf"
        data = path.read_bytes()
        # Should be truncated
        assert len(data) < 5000, "corrupt.pdf should be small (truncated)"

    def test_not_a_pdf(self):
        """not-a-pdf.pdf should actually be a PNG."""
        path = FIXTURES_OUT_DIR / "not-a-pdf.pdf"
        # Try to open as image
        img = Image.open(path)
        assert img.format == "PNG", f"Expected PNG format, got {img.format}"
        assert img.size == (100, 100)

    def test_pdf20(self):
        """PDF 2.0 file should have PDF 2.0 header."""
        path = FIXTURES_OUT_DIR / "pdf20.pdf"
        header = path.read_bytes()[:8]
        assert header == b"%PDF-2.0", f"Expected PDF-2.0 header, got {header}"

    def test_form_fields(self):
        """Form fields PDF should contain AcroForm widgets."""
        doc = _open_pdf("form-fields.pdf")
        page = doc[0]
        widgets = list(page.widgets())
        assert len(widgets) > 0, "Expected at least one widget"
        field_names = [w.field_name for w in widgets]
        assert "nama_lengkap" in field_names
        doc.close()

    def test_with_js(self):
        """with-js.pdf should contain JavaScript."""
        doc = _open_pdf("with-js.pdf")
        # Check for JavaScript in the catalog
        doc.pdf_catalog()  # noqa: B018
        # Read raw PDF to check for JavaScript
        raw = doc.tobytes(garbage=4)
        assert b"JavaScript" in raw or b"OpenAction" in raw, (
            "Expected JavaScript or OpenAction in with-js.pdf"
        )
        doc.close()


class TestAssetImages:
    """Test asset image fixtures."""

    def test_asset_red(self):
        path = ASSETS_DIR / "asset-red.png"
        if not path.exists():
            pytest.skip("asset-red.png not found")
        img = Image.open(path)
        assert img.size == (600, 200), f"Expected 600x200, got {img.size}"
        assert img.mode == "RGB"

    def test_asset_sig(self):
        path = ASSETS_DIR / "asset-sig.png"
        if not path.exists():
            pytest.skip("asset-sig.png not found")
        img = Image.open(path)
        assert img.size == (300, 100), f"Expected 300x100, got {img.size}"
        assert img.mode == "RGBA", "Signature asset should have alpha channel"

    def test_asset_jpg_exif(self):
        path = ASSETS_DIR / "asset.jpg"
        if not path.exists():
            pytest.skip("asset.jpg not found")
        img = Image.open(path)
        exif = img.getexif()
        assert exif.get(0x0112) == 6, (
            f"Expected EXIF orientation=6, got {exif.get(0x0112)}"
        )

    def test_bomb_png(self):
        """bomb.png should have huge declared dimensions."""
        path = ASSETS_DIR / "bomb.png"
        if not path.exists():
            pytest.skip("bomb.png not found")
        # Read raw bytes to avoid Pillow decompression bomb detection
        raw = path.read_bytes()
        # PNG IHDR chunk: 8-byte sig + 4-byte length + 4-byte "IHDR" + 4-byte width + 4-byte height
        assert raw.startswith(b"\x89PNG"), "Not a valid PNG"
        width = int.from_bytes(raw[16:20], "big")
        height = int.from_bytes(raw[20:24], "big")
        assert width > 10000, f"Expected huge width, got {width}"
        assert height > 10000, f"Expected huge height, got {height}"
