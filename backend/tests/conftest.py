"""Pytest fixtures for test PKI and mock services."""

from __future__ import annotations

import socket
import threading
from collections.abc import Generator
from pathlib import Path

import pytest
from asn1crypto import pem
from certomancer.integrations.animator import Animator, AnimatorArchStore
from certomancer.registry import PKIArchitecture
from certomancer.registry.config import CertomancerConfig
from werkzeug.serving import make_server

PKI_DIR = Path(__file__).resolve().parent / "pki"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
OUT_DIR = PKI_DIR / "out"
P12_DIR = OUT_DIR / "p12"
TRUST_DIR = OUT_DIR / "trust"
FIXTURES_OUT_DIR = FIXTURES_DIR / "out"
ASSETS_DIR = FIXTURES_DIR / "assets"

P12_PASSPHRASE = b"uji-rahasia"


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CertomancerAnimator:
    """Runs certomancer WSGI app in a background thread."""

    def __init__(self, port: int) -> None:
        self.port = port
        self._server: make_server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        cfg = CertomancerConfig.from_file(
            str(PKI_DIR / "certomancer.yml"),
            key_search_dir=str(PKI_DIR),
            config_search_dir=str(PKI_DIR),
            external_url_prefix=f"http://127.0.0.1:{self.port}",
        )
        arch_store = AnimatorArchStore(cfg.pki_archs)
        app = Animator(arch_store, with_web_ui=False)
        self._server = make_server("127.0.0.1", self.port, app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def tsa_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/tte-test/tsa/tsa"

    @property
    def ocsp_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/tte-test/ocsp/psre-ca"

    @property
    def crl_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/tte-test/crls/psre-ca/latest.crl"


@pytest.fixture(scope="session")
def pki_services() -> Generator[_CertomancerAnimator]:
    """Start certomancer mock services (TSA, OCSP, CRL) on a free port.

    Yields an animator with .tsa_url, .ocsp_url, .crl_url properties.
    """
    port = _find_free_port()
    animator = _CertomancerAnimator(port)
    animator.start()
    try:
        yield animator
    finally:
        animator.stop()


@pytest.fixture(scope="session")
def pki_arch(pki_services: _CertomancerAnimator) -> PKIArchitecture:
    """Return the PKIArchitecture loaded with the correct port."""
    cfg = CertomancerConfig.from_file(
        str(PKI_DIR / "certomancer.yml"),
        key_search_dir=str(PKI_DIR),
        config_search_dir=str(PKI_DIR),
        external_url_prefix=f"http://127.0.0.1:{pki_services.port}",
    )
    return cfg.get_pki_arch("tte-test")


@pytest.fixture
def p12_bytes() -> callable:
    """Return a function that reads a PKCS#12 bundle by label.

    Usage: p12_bytes("signer-valid") -> bytes
    """
    def _get(label: str) -> bytes:
        p12_path = P12_DIR / f"{label}.p12"
        if not p12_path.exists():
            msg = f"PKCS#12 not found: {label}.p12 (run 'make pki' first)"
            raise FileNotFoundError(msg)
        return p12_path.read_bytes()
    return _get


@pytest.fixture
def trust_dir() -> Path:
    """Return the path to the trust store directory."""
    if not TRUST_DIR.exists():
        msg = f"Trust directory not found: {TRUST_DIR} (run 'make pki' first)"
        raise FileNotFoundError(msg)
    return TRUST_DIR


@pytest.fixture
def signer_cert(pki_arch: PKIArchitecture) -> callable:
    """Return a function that gets a signer certificate PEM by label.

    Usage: signer_cert("signer-valid") -> str (PEM)
    """
    def _get(label: str) -> str:
        cert = pki_arch.get_cert(label)
        return pem.armor("CERTIFICATE", cert.dump()).decode()
    return _get


@pytest.fixture
def fixture_pdf() -> callable:
    """Return a function that reads a fixture PDF by name.

    Usage: fixture_pdf("a4.pdf") -> bytes
    """
    def _get(name: str) -> bytes:
        path = FIXTURES_OUT_DIR / name
        if not path.exists():
            msg = f"Fixture PDF not found: {name} (run 'make fixtures' first)"
            raise FileNotFoundError(msg)
        return path.read_bytes()
    return _get
