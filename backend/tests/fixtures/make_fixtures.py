#!/usr/bin/env python3
"""Generate test PDF fixtures and asset images.

Output goes to backend/tests/fixtures/out/ and backend/tests/fixtures/assets/.

Usage:
    python make_fixtures.py [--large] [--force]

Idempotent: re-running overwrites output.
"""

from __future__ import annotations

import argparse
import io
import shutil
import struct
import zlib
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz  # noqa: N812

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent / "out"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Standard page sizes in points (width x height)
PAGE_SIZES = {
    "a4": (595, 842),
    "letter": (612, 792),
    "legal": (612, 1008),
    "f4": (595, 935),  # F4 = 210mm x 330mm
    "a4-landscape": (842, 595),
}


def _add_corner_labels(page: fitz.Page, label: str) -> None:
    """Add text labels at each corner of the page."""
    rect = page.rect
    font_size = 10
    points = {
        "top-left": (rect.x0 + 10, rect.y0 + 15),
        "top-right": (rect.x1 - 80, rect.y0 + 15),
        "bottom-left": (rect.x0 + 10, rect.y1 - 10),
        "bottom-right": (rect.x1 - 80, rect.y1 - 10),
    }
    for corner, pos in points.items():
        page.insert_text(
            pos,
            f"{label} - {corner}",
            fontsize=font_size,
            color=(0, 0, 0),
        )


def _make_standard_pages() -> None:
    """Generate standard page size PDFs."""
    for name, (w, h) in PAGE_SIZES.items():
        doc = fitz.open()
        page = doc.new_page(width=w, height=h)
        _add_corner_labels(page, name)
        doc.save(str(OUT_DIR / f"{name}.pdf"), garbage=4, deflate=True)
        doc.close()
        print(f"  {name}.pdf ({w}x{h})")


def _make_rotated_pages() -> None:
    """Generate PDFs with /Rotate."""
    rotations = {
        "rot90": 90,
        "rot180": 180,
        "rot270": 270,
    }
    for name, rotation in rotations.items():
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.set_rotation(rotation)
        _add_corner_labels(page, name)
        doc.save(str(OUT_DIR / f"{name}.pdf"), garbage=4, deflate=True)
        doc.close()
        print(f"  {name}.pdf (rotation={rotation})")


def _make_cropbox_offset() -> None:
    """Generate PDF with MediaBox A4 and CropBox offset."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Set CropBox offset: [50, 60, 545, 780]
    page.set_cropbox(fitz.Rect(50, 60, 545, 780))
    _add_corner_labels(page, "cropbox-offset")
    doc.save(str(OUT_DIR / "cropbox-offset.pdf"), garbage=4, deflate=True)
    doc.close()
    print("  cropbox-offset.pdf")


def _make_cropbox_offset_rot90() -> None:
    """Generate PDF with CropBox offset + rotation 90."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.set_rotation(90)
    page.set_cropbox(fitz.Rect(50, 60, 545, 780))
    _add_corner_labels(page, "cropbox-offset-rot90")
    doc.save(str(OUT_DIR / "cropbox-offset-rot90.pdf"), garbage=4, deflate=True)
    doc.close()
    print("  cropbox-offset-rot90.pdf")


def _make_multipage(count: int, name: str) -> None:
    """Generate a multi-page PDF."""
    doc = fitz.open()
    for i in range(count):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (72, 72 + i * 10),
            f"Page {i + 1} of {count}",
            fontsize=12,
            color=(0, 0, 0),
        )
    doc.save(str(OUT_DIR / f"{name}.pdf"), garbage=4, deflate=True)
    doc.close()
    print(f"  {name}.pdf ({count} pages)")


def _make_inherited_boxes() -> None:
    """Generate PDF with MediaBox/Rotate inherited from /Pages node.

    Creates a document where the page inherits rotation from the parent node.
    """
    # We need to manually construct the PDF to set /Rotate on /Pages
    # PyMuPDF doesn't expose /Pages attributes directly, so we build raw PDF
    doc = fitz.open()
    # Add a page, then modify the PDF to set Rotate on Pages
    page = doc.new_page(width=595, height=842)
    _add_corner_labels(page, "inherited-boxes")

    # Save, then modify the raw PDF to move Rotate to Pages
    tmp_path = OUT_DIR / "_inherited_tmp.pdf"
    doc.save(str(tmp_path), garbage=4, deflate=True)
    doc.close()

    # Read and modify the raw PDF content
    content = tmp_path.read_bytes()
    # Replace /Rotate in page dict with /Rotate in Pages dict
    # Simple approach: find the page dict and move /Rotate up
    content_str = content.decode("latin-1")
    # Remove /Rotate from page level and add to Pages level
    content_str = content_str.replace("/Rotate 0", "")
    # Add /Rotate 90 to the Pages object
    content_str = content_str.replace(
        "/Type /Pages",
        "/Type /Pages /Rotate 90",
    )
    (OUT_DIR / "inherited-boxes.pdf").write_bytes(content_str.encode("latin-1"))
    tmp_path.unlink()
    print("  inherited-boxes.pdf")


def _make_form_fields() -> None:
    """Generate PDF with AcroForm text field."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Insert a text widget (AcroForm field)
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "nama_lengkap"
    widget.field_value = ""
    widget.rect = fitz.Rect(100, 100, 400, 140)
    widget.border_color = (0, 0, 0)
    widget.fill_color = (0.95, 0.95, 0.95)
    widget.text_color = (0, 0, 0)
    widget.font_size = 12
    page.add_widget(widget)
    doc.save(str(OUT_DIR / "form-fields.pdf"), garbage=4, deflate=True)
    doc.close()
    print("  form-fields.pdf")


def _make_with_js() -> None:
    """Generate PDF with OpenAction JavaScript."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "This PDF has OpenAction JavaScript", fontsize=12)
    doc.set_metadata({"title": "With JS"})
    doc.save(str(OUT_DIR / "with-js.pdf"), garbage=4, deflate=True)
    doc.close()

    # Inject the OpenAction via raw PDF manipulation
    content = (OUT_DIR / "with-js.pdf").read_bytes()
    content_str = content.decode("latin-1")
    # PyMuPDF writes /Type/Catalog (no space)
    if "/Type/Catalog" in content_str:
        content_str = content_str.replace(
            "/Type/Catalog",
            "/Type/Catalog /OpenAction << /S /JavaScript /JS "
            "(app.alert('Hello from JavaScript!');) >>",
        )
    (OUT_DIR / "with-js.pdf").write_bytes(content_str.encode("latin-1"))
    print("  with-js.pdf")


def _make_encrypted() -> None:
    """Generate password-protected PDF (AES-256)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "This PDF is encrypted", fontsize=12)
    doc.save(
        str(OUT_DIR / "encrypted.pdf"),
        garbage=4,
        deflate=True,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="rahasia123",
        owner_pw="owner123",
    )
    doc.close()
    print("  encrypted.pdf")


def _make_corrupt() -> None:
    """Generate a truncated/corrupt PDF."""
    # Create a minimal valid PDF first, then truncate it
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "This PDF will be truncated", fontsize=12)
    tmp_path = OUT_DIR / "_corrupt_tmp.pdf"
    doc.save(str(tmp_path), garbage=4, deflate=True)
    doc.close()

    # Truncate at roughly 60% of the file
    content = tmp_path.read_bytes()
    truncate_at = int(len(content) * 0.6)
    # Find the last complete newline before truncation point
    truncate_at = content.rfind(b"\n", 0, truncate_at)
    if truncate_at < 0:
        truncate_at = int(len(content) * 0.6)
    (OUT_DIR / "corrupt.pdf").write_bytes(content[:truncate_at])
    tmp_path.unlink()
    print("  corrupt.pdf")


def _make_not_a_pdf() -> None:
    """Generate a PNG file with .pdf extension."""
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(str(OUT_DIR / "not-a-pdf.pdf"), format="PNG")
    print("  not-a-pdf.pdf (actually PNG)")


def _make_pdf20() -> None:
    """Generate a PDF 2.0 file."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "PDF 2.0 document", fontsize=12)
    # Set PDF version to 2.0
    doc.save(
        str(OUT_DIR / "pdf20.pdf"),
        garbage=4,
        deflate=True,
    )
    doc.close()

    # Modify the header to PDF 2.0
    content = (OUT_DIR / "pdf20.pdf").read_bytes()
    content = content.replace(b"%PDF-1.7", b"%PDF-2.0", 1)
    content = content.replace(b"%PDF-1.4", b"%PDF-2.0", 1)
    (OUT_DIR / "pdf20.pdf").write_bytes(content)
    print("  pdf20.pdf")


def _make_large_21mb() -> None:
    """Generate a >20 MB PDF with uncompressed noise image."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Create a large noise image (approximately 21 MB when stored)
    # A 2000x1400 RGB image with noise takes about 8.4 MB uncompressed
    # We'll use a larger image and store it with minimal compression
    width, height = 2500, 1800
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    # Fill with noise-like pattern
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            r = (x * y) % 256
            g = (x + y) % 256
            b = (x * y * 7) % 256
            draw.rectangle([x, y, x + 1, y + 1], fill=(r, g, b))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Insert the image into the PDF
    rect = fitz.Rect(0, 0, 595, 842)
    page.insert_image(rect, stream=img_bytes.read())

    doc.save(str(OUT_DIR / "large-21mb.pdf"), garbage=4, deflate=False)
    doc.close()

    size_mb = (OUT_DIR / "large-21mb.pdf").stat().st_size / (1024 * 1024)
    print(f"  large-21mb.pdf ({size_mb:.1f} MB)")


# ─── Asset Images ─────────────────────────────────────────────────────────────


def _make_asset_images() -> None:
    """Generate test asset images."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # asset-red.png: solid red 600x200 with blue square at top-left as orientation marker
    img = Image.new("RGB", (600, 200), color=(255, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 30, 30], fill=(0, 0, 255))  # Blue square marker
    img.save(str(ASSETS_DIR / "asset-red.png"), format="PNG")
    print("  asset-red.png (600x200 red with blue corner marker)")

    # asset-sig.png: transparent signature-like image
    img = Image.new("RGBA", (300, 100), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw a simple squiggle
    for i in range(10, 290, 5):
        y = 30 + (i % 20)
        draw.rectangle([i, y, i + 2, y + 2], fill=(0, 0, 0, 200))
    img.save(str(ASSETS_DIR / "asset-sig.png"), format="PNG")
    print("  asset-sig.png (300x100 transparent with marks)")

    # asset.jpg: JPEG with EXIF orientation=6 (rotated 90 CW)
    img = Image.new("RGB", (200, 400), color=(0, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "EXIF Orientation 6", fill=(0, 0, 0))
    # Save with EXIF orientation tag
    exif_data = Image.Exif()
    exif_data[0x0112] = 6  # Orientation tag
    img.save(
        str(ASSETS_DIR / "asset.jpg"),
        format="JPEG",
        quality=85,
        exif=exif_data.tobytes(),
    )
    print("  asset.jpg (200x400 green with EXIF orientation=6)")

    # bomb.png: decompression bomb (small file, huge declared dimensions)
    _make_decompression_bomb()

    print(f"  Assets generated in {ASSETS_DIR}")


def _make_decompression_bomb() -> None:
    """Create a PNG decompression bomb: small file with huge dimensions.

    This creates a minimal PNG with a very large width/height in IHDR,
    which can cause denial-of-service when decoded.
    """
    # Minimal PNG with huge dimensions (100000 x 100000)
    # PNG structure: signature + IHDR + IDAT (empty) + IEND
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk: width=100000, height=100000, bit_depth=8, color_type=2 (RGB)
    ihdr_data = struct.pack(">IIBBBBB", 100000, 100000, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    # IDAT chunk: minimal compressed data (one empty scanline)
    compressed = zlib.compress(b"\x00")  # filter byte only
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

    # IEND chunk
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    bomb_data = sig + ihdr + idat + iend
    (ASSETS_DIR / "bomb.png").write_bytes(bomb_data)
    print(f"  bomb.png ({len(bomb_data)} bytes, declares 100000x100000)")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test PDF fixtures and assets")
    parser.add_argument(
        "--large",
        action="store_true",
        help="Generate large files (>20 MB)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if output exists",
    )
    args = parser.parse_args()

    # Clean and recreate output directories
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    print("=== Generating PDF fixtures ===")
    _make_standard_pages()
    _make_rotated_pages()
    _make_cropbox_offset()
    _make_cropbox_offset_rot90()
    _make_multipage(20, "multipage-20")
    _make_multipage(200, "multipage-200")
    _make_inherited_boxes()
    _make_form_fields()
    _make_with_js()
    _make_encrypted()
    _make_corrupt()
    _make_not_a_pdf()
    _make_pdf20()

    if args.large:
        _make_large_21mb()

    print("\n=== Generating asset images ===")
    _make_asset_images()

    print(f"\nAll fixtures generated in {OUT_DIR}")
    print(f"Assets generated in {ASSETS_DIR}")


if __name__ == "__main__":
    main()
