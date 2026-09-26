#!/usr/bin/env python3
"""Build test PKI using certomancer.

Generates all key files, certificates, PKCS#12 bundles, and trust store
into backend/tests/pki/out/.

Usage:
    python build_pki.py [--port PORT]

Idempotent: re-running overwrites output.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from asn1crypto import pem
from certomancer.registry.config import CertomancerConfig
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

PKI_DIR = Path(__file__).resolve().parent
OUT_DIR = PKI_DIR / "out"
KEYS_DIR = PKI_DIR / "keys"
CONFIG_FILE = PKI_DIR / "certomancer.yml"
P12_PASSPHRASE = b"uji-rahasia"

# Key specifications: (label, algorithm, key_size_or_curve)
KEY_SPECS: list[tuple[str, str, int | str]] = [
    ("tte-test-root", "rsa", 4096),
    ("psre-ca", "rsa", 4096),
    ("signer-valid", "rsa", 2048),
    ("signer-ecdsa", "ec", "P-256"),
    ("signer-expired", "rsa", 2048),
    ("signer-notyet", "rsa", 2048),
    ("signer-revoked", "rsa", 2048),
    ("signer-nokeyusage", "rsa", 2048),
    ("server-seal", "rsa", 2048),
    ("tsa", "rsa", 2048),
    ("ocsp", "rsa", 2048),
    ("untrusted-root", "rsa", 4096),
    ("signer-untrusted", "rsa", 2048),
]

# Labels for which entities to export as PKCS#12
P12_LABELS = [
    "signer-valid",
    "signer-ecdsa",
    "signer-expired",
    "signer-notyet",
    "signer-revoked",
    "signer-nokeyusage",
    "server-seal",
    "tsa",
    "ocsp",
]

# Labels for which entities to include in the trust store
TRUST_LABELS = ["tte-test-root", "psre-ca"]


def _generate_key(label: str, algorithm: str, key_size_or_curve: int | str):
    """Generate a private key."""
    if algorithm == "rsa":
        assert isinstance(key_size_or_curve, int)
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size_or_curve,
        )
    elif algorithm == "ec":
        curve_name = str(key_size_or_curve)
        curve_map = {
            "P-256": ec.SECP256R1(),
            "P-384": ec.SECP384R1(),
            "P-521": ec.SECP521R1(),
        }
        curve = curve_map.get(curve_name)
        if curve is None:
            msg = f"Unknown EC curve: {curve_name}"
            raise ValueError(msg)
        return ec.generate_private_key(curve)
    else:
        msg = f"Unknown algorithm: {algorithm}"
        raise ValueError(msg)


def _generate_keys() -> None:
    """Generate all key files into KEYS_DIR."""
    if KEYS_DIR.exists():
        shutil.rmtree(KEYS_DIR)
    KEYS_DIR.mkdir(parents=True)

    for label, algorithm, key_size_or_curve in KEY_SPECS:
        key = _generate_key(label, algorithm, key_size_or_curve)
        key_path = KEYS_DIR / f"{label}.pem"
        key_bytes = key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        key_path.write_bytes(key_bytes)
        print(f"  Key: {label}.pem ({algorithm})")


def build_pki(port: int = 20888) -> None:
    # Clean and recreate output directory
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    # Step 1: Generate keys
    print("=== Generating keys ===")
    _generate_keys()

    # Step 2: Load certomancer config and build architecture
    print("\n=== Building PKI architecture ===")
    cfg = CertomancerConfig.from_file(
        str(CONFIG_FILE),
        key_search_dir=str(PKI_DIR),
        config_search_dir=str(PKI_DIR),
        external_url_prefix=f"http://127.0.0.1:{port}",
    )
    arch = cfg.get_pki_arch("tte-test")

    # Step 3: Export certificates
    print("\n=== Exporting certificates ===")
    certs_dir = OUT_DIR / "certs"
    certs_dir.mkdir()
    p12_dir = OUT_DIR / "p12"
    p12_dir.mkdir()
    trust_dir = OUT_DIR / "trust"
    trust_dir.mkdir()

    # Get all cert labels from the architecture
    all_cert_labels = list(arch._cert_labels_by_subject.keys())

    # Export all certificates as PEM
    for label in all_cert_labels:
        try:
            cert = arch.get_cert(label)
            cert_path = certs_dir / f"{label}.pem"
            cert_path.write_text(pem.armor("CERTIFICATE", cert.dump()).decode() + "\n")
            print(f"  Cert: {label}.pem")
        except Exception as e:
            print(f"  [WARN] Could not export cert '{label}': {e}", file=sys.stderr)

    # Export full chain PEM files
    for label in all_cert_labels:
        try:
            chain = arch.get_chain(label)
            chain_parts = []
            for c_label in chain:
                c_cert = arch.get_cert(c_label)
                chain_parts.append(pem.armor("CERTIFICATE", c_cert.dump()).decode())
            chain_path = certs_dir / f"{label}-chain.pem"
            chain_path.write_text("\n".join(chain_parts) + "\n")
            print(f"  Chain: {label}-chain.pem")
        except Exception as e:
            print(f"  [WARN] Could not export chain '{label}': {e}", file=sys.stderr)

    # Step 4: Export PKCS#12 bundles
    print("\n=== Exporting PKCS#12 bundles ===")
    for label in P12_LABELS:
        try:
            p12_bytes = arch.package_pkcs12(label, password=P12_PASSPHRASE)
            p12_path = p12_dir / f"{label}.p12"
            p12_path.write_bytes(p12_bytes)
            print(f"  PKCS#12: {label}.p12")
        except Exception as e:
            print(f"  [WARN] Could not export PKCS#12 '{label}': {e}", file=sys.stderr)

    # Step 5: Export trust store
    print("\n=== Exporting trust store ===")
    for label in TRUST_LABELS:
        try:
            cert = arch.get_cert(label)
            trust_path = trust_dir / f"{label}.pem"
            trust_path.write_text(pem.armor("CERTIFICATE", cert.dump()).decode() + "\n")
            print(f"  Trust: {label}.pem")
        except Exception as e:
            print(f"  [WARN] Could not export trust '{label}': {e}", file=sys.stderr)

    print(f"\nPKI generated in {OUT_DIR}")
    print(f"  Certificates: {certs_dir}")
    print(f"  PKCS#12 bundles: {p12_dir}")
    print(f"  Trust store: {trust_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build test PKI")
    parser.add_argument(
        "--port",
        type=int,
        default=20888,
        help="Port for mock TSA/OCSP/CRL services (default: 20888)",
    )
    args = parser.parse_args()
    build_pki(args.port)


if __name__ == "__main__":
    main()
