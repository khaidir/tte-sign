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
import sys
import threading
import time
from typing import Any

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


results: dict[str, dict[str, object]] = {}
steps: list[dict[str, object]] = []


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
    versions: dict[str, str] = {}

    t1 = step("import_fitz")
    import pymupdf  # type: ignore[import-untyped]  # noqa: F811
    end_step(t1)
    versions["pymupdf"] = pymupdf.version  # type: ignore[attr-defined]

    t2 = step("import_pyhanko")
    import pyhanko  # type: ignore[import-untyped]  # noqa: F811
    try:
        versions["pyhanko"] = pyhanko.__version__  # type: ignore[attr-defined]
    except AttributeError:
        # pyHanko may not expose __version__; try importlib
        from importlib.metadata import version as _importlib_version
        versions["pyhanko"] = _importlib_version("pyhanko")
    end_step(t2)

    t3 = step("import_pillow")
    from PIL import Image  # type: ignore[import-untyped]  # noqa: F811
    end_step(t3)
    versions["pillow"] = Image.__version__  # type: ignore[attr-defined]

    t4 = step("import_cryptography")
    import cryptography  # type: ignore[import-untyped]  # noqa: F811
    end_step(t4)
    versions["cryptography"] = cryptography.__version__  # type: ignore[attr-defined]

    t5 = step("import_fastapi")
    import fastapi  # type: ignore[import-untyped]  # noqa: F811
    end_step(t5)
    versions["fastapi"] = fastapi.__version__  # type: ignore[attr-defined]

    t6 = step("import_lxml")
    import lxml  # type: ignore[import-untyped]  # noqa: F811
    end_step(t6)
    versions["lxml"] = lxml.__version__  # type: ignore[attr-defined]

    t7 = step("import_aiohttp")
    import aiohttp  # type: ignore[import-untyped]  # noqa: F811
    end_step(t7)
    versions["aiohttp"] = aiohttp.__version__  # type: ignore[attr-defined]

    t8 = step("import_fonttools")
    import fontTools  # type: ignore[import-untyped]  # noqa: F811
    end_step(t8)
    versions["fonttools"] = fontTools.__version__  # type: ignore[attr-defined]

    return versions


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: Create PDF with PyMuPDF
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_pdf() -> bytes:
    """Create a 3-page PDF with varied page properties."""
    t = step("create_pdf")
    import pymupdf  # type: ignore[import-untyped]

    doc = pymupdf.Document()  # type: ignore[attr-defined]

    # Page 1: A4 portrait, no rotation
    page1 = doc.new_page(width=595.28, height=841.89)  # type: ignore[attr-defined]
    page1.insert_text(  # type: ignore[attr-defined]
        pymupdf.Point(72, 72),  # type: ignore[attr-defined]
        "Halaman 1 — Stamp Test",
        fontsize=16,
        fontname="helv",
    )

    # Page 2: A4 portrait, /Rotate 90
    page2 = doc.new_page(width=595.28, height=841.89)  # type: ignore[attr-defined]
    page2.set_rotation(90)  # type: ignore[attr-defined]
    page2.insert_text(  # type: ignore[attr-defined]
        pymupdf.Point(72, 72),  # type: ignore[attr-defined]
        "Halaman 2 — Rotated 90°",
        fontsize=16,
        fontname="helv",
    )

    # Page 3: A4 portrait, offset CropBox
    page3 = doc.new_page(width=595.28, height=841.89)  # type: ignore[attr-defined]
    page3.set_cropbox(pymupdf.Rect(36, 36, 559.28, 805.89))  # type: ignore[attr-defined]
    page3.insert_text(  # type: ignore[attr-defined]
        pymupdf.Point(72, 72),  # type: ignore[attr-defined]
        "Halaman 3 — Offset CropBox",
        fontsize=16,
        fontname="helv",
    )

    pdf_bytes: bytes = doc.tobytes()  # type: ignore[attr-defined]
    doc.close()  # type: ignore[attr-defined]
    end_step(t)
    return pdf_bytes  # type: ignore[return-type]


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Create stamp PNG with Pillow
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_stamp_png() -> bytes:
    """Create a simple stamp image (red circle + text) with Pillow."""
    t = step("create_stamp_png")
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

    size = (200, 100)
    img = Image.new("RGBA", size, (255, 255, 255, 0))  # type: ignore[attr-defined]
    draw = ImageDraw.Draw(img)  # type: ignore[attr-defined]

    # Red rounded rectangle
    draw.rounded_rectangle([(0, 0), (199, 99)], radius=10, outline=(220, 40, 40, 255), width=3)  # type: ignore[attr-defined]

    # Text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)  # type: ignore[attr-defined]
    except (IOError, OSError):
        font = ImageFont.load_default()  # type: ignore[attr-defined]

    bbox: Any = draw.textbbox((0, 0), "TTE PDF", font=font)  # type: ignore[attr-defined]
    tw: int = bbox[2] - bbox[0]  # type: ignore[operator]
    th: int = bbox[3] - bbox[1]  # type: ignore[operator]
    draw.text(((size[0] - tw) / 2, (size[1] - th) / 2 - 10), "TTE PDF", fill=(220, 40, 40, 255), font=font)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    img.save(buf, format="PNG")  # type: ignore[attr-defined]
    end_step(t)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: Stamp PNG onto PDF pages
# ═══════════════════════════════════════════════════════════════════════════════

def step_stamp_pdf(pdf_bytes: bytes, stamp_png: bytes) -> bytes:
    """Stamp the PNG onto pages 1 and 2 using PyMuPDF."""
    t = step("stamp_pdf")
    import pymupdf  # type: ignore[import-untyped]

    doc = pymupdf.Document(stream=pdf_bytes, filetype="pdf")  # type: ignore[attr-defined]

    for page_num in [0, 1]:
        page = doc[page_num]  # type: ignore[attr-defined]
        rect = page.rect  # type: ignore[attr-defined]
        # Place stamp at top-right corner with margin
        stamp_w = 150
        stamp_h = 75
        x0 = rect.width - stamp_w - 36  # type: ignore[attr-defined]
        y0 = 36
        r = pymupdf.Rect(x0, y0, x0 + stamp_w, y0 + stamp_h)  # type: ignore[attr-defined]
        page.insert_image(r, stream=stamp_png)  # type: ignore[attr-defined]

    stamped: bytes = doc.tobytes()  # type: ignore[attr-defined]
    doc.close()  # type: ignore[attr-defined]
    end_step(t)
    return stamped  # type: ignore[return-type]


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: Create PKI in-memory (cryptography)
# ═══════════════════════════════════════════════════════════════════════════════

def step_create_pki() -> tuple[bytes, bytes, bytes]:
    """
    Create root CA + signer cert in-memory.
    Returns (pkcs12_bytes, root_cert_pem, passphrase).
    """
    t = step("create_pki")
    from cryptography.hazmat.primitives import hashes, serialization  # type: ignore[import-untyped]
    from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore[import-untyped]
    from cryptography import x509  # type: ignore[import-untyped]
    from cryptography.x509.oid import NameOID  # type: ignore[import-untyped]
    import datetime

    # Root CA
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # type: ignore[attr-defined]
    root_subject = issuer = x509.Name([  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TTE PDF Spike Root CA"),  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.COMMON_NAME, "Spike Root CA"),  # type: ignore[attr-defined]
    ])
    root_cert: Any = (  # type: ignore[var-annotated]
        x509.CertificateBuilder()  # type: ignore[attr-defined]
        .subject_name(root_subject)
        .issuer_name(issuer)
        .public_key(root_key.public_key())  # type: ignore[attr-defined]
        .serial_number(1)
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)  # type: ignore[attr-defined]
        .sign(root_key, hashes.SHA256())  # type: ignore[attr-defined]
    )

    # Signer cert
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # type: ignore[attr-defined]
    signer_subject = x509.Name([  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TTE PDF Spike"),  # type: ignore[attr-defined]
        x509.NameAttribute(NameOID.COMMON_NAME, "Spike Signer"),  # type: ignore[attr-defined]
    ])
    signer_cert: Any = (  # type: ignore[var-annotated]
        x509.CertificateBuilder()  # type: ignore[attr-defined]
        .subject_name(signer_subject)
        .issuer_name(root_subject)
        .public_key(signer_key.public_key())  # type: ignore[attr-defined]
        .serial_number(2)
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)  # type: ignore[attr-defined]
        .add_extension(
            x509.KeyUsage(  # type: ignore[attr-defined]
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
        .sign(root_key, hashes.SHA256())  # type: ignore[attr-defined]
    )

    # Export PKCS#12
    passphrase = b"spike-passphrase-123"
    from cryptography.hazmat.primitives.serialization import pkcs12  # type: ignore[import-untyped]
    pkcs12_bytes: bytes = pkcs12.serialize_key_and_certificates(  # type: ignore[attr-defined]
        name=b"spike-signer",
        key=signer_key,
        cert=signer_cert,
        cas=[root_cert],
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),  # type: ignore[attr-defined]
    )

    root_pem: bytes = root_cert.public_bytes(serialization.Encoding.PEM)  # type: ignore[attr-defined]

    end_step(t)
    return pkcs12_bytes, root_pem, passphrase  # type: ignore[return-type]


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
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter  # type: ignore[import-untyped]
    from pyhanko.sign import signers, fields  # type: ignore[import-untyped]

    # Load signer from PKCS#12 data
    signer = signers.SimpleSigner.load_pkcs12_data(  # type: ignore[attr-defined]
        pkcs12_bytes=pkcs12,
        other_certs=None,
        passphrase=passphrase,
    )

    # Create signature appearance from PNG
    from PIL import Image  # type: ignore[import-untyped]
    from pyhanko.pdf_utils.images import PdfImage  # type: ignore[import-untyped]
    from pyhanko.stamp import StaticStampStyle  # type: ignore[import-untyped]
    from pyhanko.pdf_utils.layout import BoxConstraints  # type: ignore[import-untyped]
    img = Image.open(io.BytesIO(stamp_png))  # type: ignore[attr-defined]
    pdf_img = PdfImage(img, box=BoxConstraints(width=150, height=75))  # type: ignore[attr-defined]
    stamp_style = StaticStampStyle(background=pdf_img)  # type: ignore[attr-defined]

    # Sign using PdfSigner with stamp_style
    from pyhanko.sign.signers.pdf_signer import PdfSigner  # type: ignore[import-untyped]
    w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))  # type: ignore[attr-defined]
    out = io.BytesIO()
    signer_obj = PdfSigner(  # type: ignore[attr-defined]
        signers.PdfSignatureMetadata(field_name="Signature1"),  # type: ignore[attr-defined]
        signer=signer,
        stamp_style=stamp_style,
    )
    signer_obj.sign_pdf(w, output=out)  # type: ignore[attr-defined]

    signed = out.getvalue()
    end_step(t)
    return signed


# ═══════════════════════════════════════════════════════════════════════════════
# Step 7: Verify PAdES signature
# ═══════════════════════════════════════════════════════════════════════════════

def step_pades_verify(signed_pdf: bytes, root_pem: bytes) -> dict[str, object]:
    """Verify PAdES signature using pyHanko with root as trust anchor."""
    t = step("pades_verify")
    from pyhanko_certvalidator import ValidationContext  # type: ignore[import-untyped]
    from pyhanko.sign.validation import validate_pdf_signature  # type: ignore[import-untyped]
    from pyhanko.pdf_utils.reader import PdfFileReader  # type: ignore[import-untyped]
    from pyhanko.keys import load_certs_from_pemder_data  # type: ignore[import-untyped]

    # Load root cert
    root_certs = load_certs_from_pemder_data(root_pem)  # type: ignore[attr-defined]

    # Create validation context
    vc = ValidationContext(trust_roots=root_certs)  # type: ignore[attr-defined]

    # Read signed PDF
    r = PdfFileReader(io.BytesIO(signed_pdf))  # type: ignore[attr-defined]

    # Get embedded signature
    sigs = r.embedded_signatures  # type: ignore[attr-defined]
    if not sigs:
        end_step(t, status="fail", detail="No embedded signatures found")
        return {"found": False}

    sig: Any = sigs[0]  # type: ignore[var-annotated]
    status = validate_pdf_signature(sig, vc)  # type: ignore[attr-defined]

    result: dict[str, object] = {
        "found": True,
        "field_name": sig.field_name,  # type: ignore[attr-defined]
        "intact": status.intact,  # type: ignore[attr-defined]
        "valid": status.valid,  # type: ignore[attr-defined]
        "trusted": status.trusted,  # type: ignore[attr-defined]
        "summary": str(status.summary()),  # type: ignore[attr-defined]
    }
    end_step(t)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Step 8: Render page to PNG and verify pixel size
# ═══════════════════════════════════════════════════════════════════════════════

def step_render_page(pdf_bytes: bytes) -> dict[str, object]:
    """Render page 1 to PNG and verify dimensions."""
    t = step("render_page")
    import pymupdf  # type: ignore[import-untyped]

    doc = pymupdf.Document(stream=pdf_bytes, filetype="pdf")  # type: ignore[attr-defined]
    page = doc[0]  # type: ignore[attr-defined]

    # Render at 150 DPI
    zoom = 150 / 72
    mat = pymupdf.Matrix(zoom, zoom)  # type: ignore[attr-defined]
    pix = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]

    result: dict[str, object] = {
        "width_px": pix.width,  # type: ignore[attr-defined]
        "height_px": pix.height,  # type: ignore[attr-defined]
        "expected_width": int(595.28 * zoom),
        "expected_height": int(841.89 * zoom),
        "match": abs(pix.width - int(595.28 * zoom)) <= 1 and abs(pix.height - int(841.89 * zoom)) <= 1,  # type: ignore[attr-defined]
    }
    doc.close()  # type: ignore[attr-defined]
    end_step(t)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Step 9: FastAPI health check via uvicorn subprocess
# ═══════════════════════════════════════════════════════════════════════════════

def step_fastapi_health() -> dict[str, object]:
    """Start uvicorn in a thread, call /health, then stop."""
    t = step("fastapi_health")
    from fastapi import FastAPI  # type: ignore[import-untyped]

    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    import uvicorn  # type: ignore[import-untyped]
    import urllib.request
    import urllib.error
    import json

    # Run uvicorn in a thread
    server_config = uvicorn.Config(app, host="127.0.0.1", port=18999, log_level="error")  # type: ignore[attr-defined]
    server = uvicorn.Server(server_config)  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    for _ in range(50):
        time.sleep(0.05)
        try:
            r = urllib.request.urlopen("http://127.0.0.1:18999/health", timeout=2)
            result: dict[str, object] = {"status_code": r.status, "body": json.loads(r.read().decode())}
            server.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5)
            end_step(t)
            return result
        except (urllib.error.URLError, OSError):
            continue

    server.should_exit = True  # type: ignore[attr-defined]
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
    verify_result: dict[str, object] = step_pades_verify(signed_pdf, root_pem)
    print(f"  Found: {verify_result.get('found')}")
    print(f"  Intact: {verify_result.get('intact')}")
    print(f"  Valid: {verify_result.get('valid')}")
    print(f"  Trusted: {verify_result.get('trusted')}")
    print(f"  Summary: {verify_result.get('summary')}")

    # Step 8: Render
    print("\n--- Step 8: Render page to PNG ---")
    render_result: dict[str, object] = step_render_page(pdf_bytes)
    print(f"  Rendered: {render_result['width_px']}x{render_result['height_px']} px")
    print(f"  Expected: {render_result['expected_width']}x{render_result['expected_height']} px")
    print(f"  Match: {render_result['match']}")

    # Step 9: FastAPI health
    print("\n--- Step 9: FastAPI health check ---")
    health_result: dict[str, object] = step_fastapi_health()
    print(f"  Status: {health_result.get('status_code')}")
    print(f"  Body: {health_result.get('body')}")

    overall_ms = overall.ms

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_ok = all(s.get("status") == "ok" for s in steps)
    print(f"\nOverall: {'\u2705 ALL OK' if all_ok else '\u274c SOME FAILED'}")
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
    output: dict[str, object] = {
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
