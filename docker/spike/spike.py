#!/usr/bin/env python3
"""
P02 — Spike Alpine Compatibility
=================================
Tests PyMuPDF (stamp), pyHanko (PAdES sign/verify), Pillow (render),
and FastAPI/uvicorn in a single python:3.13-alpine3.24 container.

Outputs JSON results with versions, status, and timing per step.
"""

from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# ── Timing helper ─────────────────────────────────────────────────────────────


class Timer:
    def __init__(self) -> None:
        self._start: float = 0.0
        self._elapsed: float = 0.0

    def start(self) -> None:
        self._start = time.monotonic()

    def stop(self) -> float:
        self._elapsed = time.monotonic() - self._start
        return self._elapsed

    @property
    def ms(self) -> int:
        return int(self._elapsed * 1000)


results: dict[str, dict] = {}
steps: list[dict] = []


def step(name: str) -> Timer:
    """Decorator-like context: records step start."""
    t = Timer()
    t.start()
    steps.append({"name": name, "start": time.time()})
    return t


def end_step(t: Timer, status: str = "ok", detail: str | None = None) -> None:
    """Record step end."""
    steps[-1]["duration_ms"] = t.ms
    steps[-1]["status"] = status
    if detail:
        steps[-1]["detail"] = detail


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Import versions
# ═══════════════════════════════════════════════════════════════════════════════

def step_imports() -> dict[str, str]:
    """Record versions of key packages."""
    versions = {}

    t1 = step("import_fitz")
    import pymupdf  # noqa: F811
    end_step(t1)
    versions["pymupdf"] = pymupdf.version

    t2 = step("import_pyhanko")
    import pyhanko  # noqa: F811
    try:
        versions["pyhanko"] = pyhanko.__version__
    except AttributeError:
        # pyHanko may not expose __version__; try importlib
        from importlib.metadata import version as _importlib_version
        versions["pyhanko"] = _importlib_version("pyhanko")
    end_step(t2)

    t3 = step("import_pillow")
    from PIL import Image  # noqa: F811
    end_step(t3)
    versions["pillow"] = Image.__version__

    t4 = step("import_cryptography")
    import cryptography  # noqa: F811
    end_step(t4)
    versions["cryptography"] = cryptography.__version__

    t5 = step("import_fastapi")
    import fastapi  # noqa: F811
    end_step(t5)
    versions["fastapi"] = fastapi.__version__

    t6 = step("import_lxml")
    import lxml  # noqa: F811
    end_step(t6)
    versions["lxml"] = lxml.__version__

    t7 = step("import_aiohttp")
    import aiohttp  # noqa: F811
    end_step(t7)
    versions["aiohttp"] = aiohttp.__version__

    t8 = step("import_fonttools")
    import fontTools  # noqa: F811
    end_step(t8)
    versions["fonttools"] = fontTools.__version__

    return versions


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: Create PDF with PyMuPDF
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_pdf() -> bytes:
    """Create a 3-page PDF with varied page properties."""
    t = step("create_pdf")
    import pymupdf

    doc = pymupdf.Document()

    # Page 1: A4 portrait, no rotation
    page1 = doc.new_page(width=595.28, height=841.89)
    page1.insert_text(
        pymupdf.Point(72, 72),
        "Halaman 1 — Stamp Test",
        fontsize=16,
        fontname="helv",
    )

    # Page 2: A4 portrait, /Rotate 90
    page2 = doc.new_page(width=595.28, height=841.89)
    page2.set_rotation(90)
    page2.insert_text(
        pymupdf.Point(72, 72),
        "Halaman 2 — Rotated 90°",
        fontsize=16,
        fontname="helv",
    )

    # Page 3: A4 portrait, offset CropBox
    page3 = doc.new_page(width=595.28, height=841.89)
    page3.set_cropbox(pymupdf.Rect(36, 36, 559.28, 805.89))
    page3.insert_text(
        pymupdf.Point(72, 72),
        "Halaman 3 — Offset CropBox",
        fontsize=16,
        fontname="helv",
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    end_step(t)
    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Create stamp PNG with Pillow
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_stamp_png() -> bytes:
    """Create a simple stamp image (red circle + text) with Pillow."""
    t = step("create_stamp_png")
    from PIL import Image, ImageDraw, ImageFont

    size = (200, 100)
    img = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Red rounded rectangle
    draw.rounded_rectangle([(0, 0), (199, 99)], radius=10, outline=(220, 40, 40, 255), width=3)

    # Text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except (IOError, OSError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "TTE PDF", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size[0] - tw) / 2, (size[1] - th) / 2 - 10), "TTE PDF", fill=(220, 40, 40, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    end_step(t)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: Stamp PNG onto PDF pages
# ═══════════════════════════════════════════════════════════════════════════════

def step_stamp_pdf(pdf_bytes: bytes, stamp_png: bytes) -> bytes:
    """Stamp the PNG onto pages 1 and 2 using PyMuPDF."""
    t = step("stamp_pdf")
    import pymupdf

    doc = pymupdf.Document(stream=pdf_bytes, filetype="pdf")

    for page_num in [0, 1]:
        page = doc[page_num]
        rect = page.rect
        # Place stamp at top-right corner with margin
        stamp_w = 150
        stamp_h = 75
        x0 = rect.width - stamp_w - 36
        y0 = 36
        r = pymupdf.Rect(x0, y0, x0 + stamp_w, y0 + stamp_h)
        page.insert_image(r, stream=stamp_png)

    stamped = doc.tobytes()
    doc.close()
    end_step(t)
    return stamped


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: Create PKI in-memory (cryptography)
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_pki() -> tuple[bytes, bytes]:
    """
    Create root CA + signer cert in-memory.
    Returns (pkcs12_bytes, root_cert_pem).
    """
    t = step("create_pki")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    import datetime

    # Root CA
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TTE PDF Spike Root CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Spike Root CA"),
    ])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_subject)
        .issuer_name(issuer)
        .public_key(root_key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    # Signer cert
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TTE PDF Spike"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Spike Signer"),
    ])
    signer_cert = (
        x509.CertificateBuilder()
        .subject_name(signer_subject)
        .issuer_name(root_subject)
        .public_key(signer_key.public_key())
        .serial_number(2)
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,  # nonRepudiation
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(root_key, hashes.SHA256())
    )

    # Export PKCS#12
    passphrase = b"spike-passphrase-123"
    from cryptography.hazmat.primitives.serialization import pkcs12
    pkcs12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"spike-signer",
        key=signer_key,
        cert=signer_cert,
        cas=[root_cert],
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    )

    root_pem = root_cert.public_bytes(serialization.Encoding.PEM)

    end_step(t)
    return pkcs12_bytes, root_pem, passphrase


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: PAdES B-B visible sign with pyHanko
# ═══════════════════════════════════════════════════════════════════════════════

def step_pades_sign(
    pdf_bytes: bytes,
    pkcs12: bytes,
    passphrase: bytes,
    stamp_png: bytes,
) -> bytes:
    """Sign PDF with PAdES B-B visible signature using pyHanko."""
    t = step("pades_sign")
    from pyhanko import stamp
    from pyhanko.keys import load_certs_from_pemder_data
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers, fields

    # Load signer from PKCS#12 data
    signer = signers.SimpleSigner.load_pkcs12_data(
        pkcs12_bytes=pkcs12,
        other_certs=None,
        passphrase=passphrase,
    )

    # Create signature appearance from PNG
    from PIL import Image
    from pyhanko.pdf_utils.images import PdfImage
    from pyhanko.stamp import StaticStampStyle, BaseStamp
    from pyhanko.pdf_utils.layout import SimpleBoxLayoutRule, BoxConstraints
    img = Image.open(io.BytesIO(stamp_png))
    pdf_img = PdfImage(img, box=BoxConstraints(width=150, height=75))
    stamp_style = StaticStampStyle(background=pdf_img)

    # Prepare SigFieldSpec
    w = 150
    h = 75
    field_spec = fields.SigFieldSpec(
        sig_field_name="Signature1",
        box=(595.28 - w - 36, 841.89 - h - 36, 595.28 - 36, 841.89 - 36),
        doc_mdp_update_value=None,
    )

    # Sign using PdfSigner with stamp_style
    from pyhanko.sign.signers.pdf_signer import PdfSigner
    w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    out = io.BytesIO()
    signer_obj = PdfSigner(
        signers.PdfSignatureMetadata(field_name="Signature1"),
        signer=signer,
        stamp_style=stamp_style,
    )
    signer_obj.sign_pdf(w, output=out)

    signed = out.getvalue()
    end_step(t)
    return signed


# ═══════════════════════════════════════════════════════════════════════════════
# Step 7: Verify PAdES signature
# ═══════════════════════════════════════════════════════════════════════════════

def step_pades_verify(signed_pdf: bytes, root_pem: bytes) -> dict:
    """Verify PAdES signature using pyHanko with root as trust anchor."""
    t = step("pades_verify")
    from pyhanko_certvalidator import ValidationContext
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.keys import load_certs_from_pemder_data

    # Load root cert
    root_certs = load_certs_from_pemder_data(root_pem)

    # Create validation context
    vc = ValidationContext(trust_roots=root_certs)

    # Read signed PDF
    r = PdfFileReader(io.BytesIO(signed_pdf))

    # Get embedded signature
    sigs = r.embedded_signatures
    if not sigs:
        end_step(t, status="fail", detail="No embedded signatures found")
        return {"found": False}

    sig = sigs[0]
    status = validate_pdf_signature(sig, vc)

    result = {
        "found": True,
        "field_name": sig.field_name,
        "intact": status.intact,
        "valid": status.valid,
        "trusted": status.trusted,
        "summary": str(status.summary()),
    }
    end_step(t)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Step 8: Render page to PNG and verify pixel size
# ═══════════════════════════════════════════════════════════════════════════════

def step_render_page(pdf_bytes: bytes) -> dict:
    """Render page 1 to PNG and verify dimensions."""
    t = step("render_page")
    import pymupdf

    doc = pymupdf.Document(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    # Render at 150 DPI
    zoom = 150 / 72
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    result = {
        "width_px": pix.width,
        "height_px": pix.height,
        "expected_width": int(595.28 * zoom),
        "expected_height": int(841.89 * zoom),
        "match": abs(pix.width - int(595.28 * zoom)) <= 1 and abs(pix.height - int(841.89 * zoom)) <= 1,
    }
    doc.close()
    end_step(t)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Step 9: FastAPI health check via uvicorn subprocess
# ═══════════════════════════════════════════════════════════════════════════════

def step_fastapi_health() -> dict:
    """Start uvicorn in a thread, call /health, then stop."""
    t = step("fastapi_health")
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    import uvicorn
    import urllib.request
    import json

    # Run uvicorn in a thread
    server_config = uvicorn.Config(app, host="127.0.0.1", port=18999, log_level="error")
    server = uvicorn.Server(server_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    for _ in range(50):
        time.sleep(0.05)
        try:
            r = urllib.request.urlopen("http://127.0.0.1:18999/health", timeout=2)
            result = {"status_code": r.status, "body": json.loads(r.read().decode())}
            server.should_exit = True
            thread.join(timeout=5)
            end_step(t)
            return result
        except (urllib.error.URLError, OSError):
            continue

    server.should_exit = True
    end_step(t, status="fail", detail="Server did not start in time")
    return {"status_code": 0, "body": None}


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    overall = Timer()
    overall.start()

    print("=" * 60)
    print("P02 — Spike Alpine Compatibility")
    print("=" * 60)

    # Step 1: Versions
    print("\n--- Step 1: Import versions ---")
    versions = step_imports()
    for pkg, ver in versions.items():
        print(f"  {pkg}: {ver}")

    # Step 2: Create PDF
    print("\n--- Step 2: Create PDF ---")
    pdf_bytes = step_create_pdf()
    print(f"  PDF size: {len(pdf_bytes)} bytes, {len(pdf_bytes) / 1024:.1f} KB")

    # Step 3: Create stamp PNG
    print("\n--- Step 3: Create stamp PNG ---")
    stamp_png = step_create_stamp_png()
    print(f"  PNG size: {len(stamp_png)} bytes")

    # Step 4: Stamp PDF
    print("\n--- Step 4: Stamp PDF ---")
    stamped_pdf = step_stamp_pdf(pdf_bytes, stamp_png)
    print(f"  Stamped PDF size: {len(stamped_pdf)} bytes")

    # Step 5: Create PKI
    print("\n--- Step 5: Create PKI ---")
    pkcs12, root_pem, passphrase = step_create_pki()
    print(f"  PKCS#12: {len(pkcs12)} bytes, Root PEM: {len(root_pem)} bytes")

    # Step 6: PAdES sign
    print("\n--- Step 6: PAdES B-B visible sign ---")
    signed_pdf = step_pades_sign(stamped_pdf, pkcs12, passphrase, stamp_png)
    print(f"  Signed PDF size: {len(signed_pdf)} bytes")

    # Step 7: Verify
    print("\n--- Step 7: Verify PAdES ---")
    verify_result = step_pades_verify(signed_pdf, root_pem)
    print(f"  Found: {verify_result.get('found')}")
    print(f"  Intact: {verify_result.get('intact')}")
    print(f"  Valid: {verify_result.get('valid')}")
    print(f"  Trusted: {verify_result.get('trusted')}")
    print(f"  Summary: {verify_result.get('summary')}")

    # Step 8: Render
    print("\n--- Step 8: Render page to PNG ---")
    render_result = step_render_page(pdf_bytes)
    print(f"  Rendered: {render_result['width_px']}x{render_result['height_px']} px")
    print(f"  Expected: {render_result['expected_width']}x{render_result['expected_height']} px")
    print(f"  Match: {render_result['match']}")

    # Step 9: FastAPI health
    print("\n--- Step 9: FastAPI health check ---")
    health_result = step_fastapi_health()
    print(f"  Status: {health_result.get('status_code')}")
    print(f"  Body: {health_result.get('body')}")

    overall_ms = overall.ms

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_ok = all(s.get("status") == "ok" for s in steps)
    print(f"\nOverall: {'✅ ALL OK' if all_ok else '❌ SOME FAILED'}")
    print(f"Total duration: {overall_ms} ms")

    print(f"\n{'Step':<30} {'Status':<8} {'Duration':<10}")
    print("-" * 50)
    for s in steps:
        dur = f"{s.get('duration_ms', 0)} ms"
        status = s.get("status", "?")
        print(f"{s['name']:<30} {status:<8} {dur:<10}")
        if s.get("detail"):
            print(f"  {'→ Detail:':<30} {s['detail']}")

    # JSON output
    output = {
        "spike": "P02 Alpine Compatibility",
        "overall_status": "ok" if all_ok else "fail",
        "total_duration_ms": overall_ms,
        "versions": versions,
        "verify": verify_result,
        "render": render_result,
        "health": health_result,
        "steps": steps,
    }
    print("\n--- JSON Output ---")
    print(json.dumps(output, indent=2, default=str))

    # Write to file for inspection
    out_path = "/tmp/spike-results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults written to {out_path}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
