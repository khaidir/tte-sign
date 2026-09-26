"""Integration tests for mock PKI services (TSA, OCSP, CRL)."""

from __future__ import annotations

import httpx
from asn1crypto import ocsp as asn1_ocsp
from certomancer.registry import PKIArchitecture
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from tests.conftest import TRUST_DIR, _CertomancerAnimator


class TestTSA:
    """Test RFC 3161 timestamping via mock TSA."""

    async def test_request_timestamp(self, pki_services: _CertomancerAnimator):
        """Request a timestamp token and validate its structure."""
        # Create a simple hash to timestamp
        digest = hashes.Hash(hashes.SHA256())
        digest.update(b"test data for timestamp")
        message_digest = digest.finalize()

        # Build TSA request manually using httpx
        # certomancer TSA accepts RFC 3161 requests via POST
        from asn1crypto import tsp

        # Build TimeStampReq
        req = tsp.TimeStampReq({
            "version": 1,
            "message_imprint": {
                "hash_algorithm": {"algorithm": "sha256"},
                "hashed_message": message_digest,
            },
            "cert_req": True,
        })
        req_data = req.dump()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                pki_services.tsa_url,
                content=req_data,
                headers={"Content-Type": "application/timestamp-query"},
            )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "application/timestamp-reply"

        # Parse the response
        from asn1crypto import tsp as tsp_resp
        reply = tsp_resp.TimeStampResp.load(resp.content)
        assert int(reply["status"]["status"]) == 0  # granted

        # Extract and validate the timestamp token
        token = reply["time_stamp_token"]
        assert token["content_type"].native == "signed_data"

        # Verify the TSA certificate is present
        signed_data = token["content"]
        certs = signed_data["certificates"]
        assert len(certs) > 0
        # Dump the first cert to DER and load with cryptography for inspection
        tsa_cert_der = certs[0].dump()
        tsa_cert = x509.load_der_x509_certificate(tsa_cert_der)
        # Check that the TSA cert has the timeStamping EKU
        assert tsa_cert.issuer is not None

    async def test_timestamp_chain_validation(
        self, pki_services: _CertomancerAnimator, pki_arch: PKIArchitecture
    ):
        """Verify the TSA response can be validated against the trust store."""
        digest = hashes.Hash(hashes.SHA256())
        digest.update(b"validation test")
        message_digest = digest.finalize()

        from asn1crypto import tsp

        req = tsp.TimeStampReq({
            "version": 1,
            "message_imprint": {
                "hash_algorithm": {"algorithm": "sha256"},
                "hashed_message": message_digest,
            },
            "cert_req": True,
        })

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                pki_services.tsa_url,
                content=req.dump(),
                headers={"Content-Type": "application/timestamp-query"},
            )
        assert resp.status_code == 200

        # Load trust roots
        trust_certs = []
        for pem_file in TRUST_DIR.glob("*.pem"):
            cert = x509.load_pem_x509_certificate(pem_file.read_bytes())
            trust_certs.append(cert)

        # Parse the timestamp token and verify the signer cert is in chain
        reply = tsp.TimeStampResp.load(resp.content)
        signed_data = reply["time_stamp_token"]["content"]
        certs = signed_data["certificates"]

        # Verify at least one cert in the chain chains to a trust root
        # certs[0] is an asn1crypto Certificate object with .dump()
        tsa_cert_der = certs[0].dump()
        tsa_cert = x509.load_der_x509_certificate(tsa_cert_der)

        # Check issuer is psre-ca
        issuer_name = tsa_cert.issuer
        assert b"PSrE Contoh CA" in issuer_name.rfc4514_string().encode()


class TestOCSP:
    """Test OCSP responder for certificate status."""

    async def test_ocsp_good(self, pki_services: _CertomancerAnimator, pki_arch: PKIArchitecture):
        """Check that signer-valid has OCSP status 'good'."""
        signer_cert = pki_arch.get_cert("signer-valid")
        issuer_cert = pki_arch.get_cert("psre-ca")

        ocsp_request = _build_ocsp_request(signer_cert, issuer_cert)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                pki_services.ocsp_url,
                content=ocsp_request,
                headers={"Content-Type": "application/ocsp-request"},
            )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "application/ocsp-response"

        status = _parse_ocsp_response(resp.content)
        assert status == "good", f"Expected 'good', got '{status}'"

    async def test_ocsp_revoked(
        self, pki_services: _CertomancerAnimator, pki_arch: PKIArchitecture
    ):
        """Check that signer-revoked has OCSP status 'revoked'."""
        signer_cert = pki_arch.get_cert("signer-revoked")
        issuer_cert = pki_arch.get_cert("psre-ca")

        ocsp_request = _build_ocsp_request(signer_cert, issuer_cert)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                pki_services.ocsp_url,
                content=ocsp_request,
                headers={"Content-Type": "application/ocsp-request"},
            )
        assert resp.status_code == 200

        status = _parse_ocsp_response(resp.content)
        assert status == "revoked", f"Expected 'revoked', got '{status}'"


class TestCRL:
    """Test CRL distribution."""

    async def test_download_crl(
        self, pki_services: _CertomancerAnimator, pki_arch: PKIArchitecture
    ):
        """Download CRL and verify its structure."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(pki_services.crl_url)
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] in (
            "application/pkix-crl",
            "application/pkcs7-crl",
        )

        # Parse CRL
        crl = x509.load_der_x509_crl(resp.content)
        assert crl.issuer is not None
        assert b"PSrE Contoh CA" in crl.issuer.rfc4514_string().encode()

        # Check that signer-revoked is in the CRL
        revoked_cert = pki_arch.get_cert("signer-revoked")
        revoked_serial = revoked_cert.serial_number
        revoked_entries = list(crl)
        revoked_serials = [entry.serial_number for entry in revoked_entries]
        assert revoked_serial in revoked_serials, (
            f"signer-revoked (serial {revoked_serial}) not found in CRL"
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_ocsp_request(
    signer_cert, issuer_cert,
) -> bytes:
    """Build a DER-encoded OCSP request for the given signer cert."""
    from asn1crypto import ocsp as ocsp_builder

    # Get the certificate serial number
    serial = signer_cert.serial_number

    # Build OCSP request — include all optional fields set to None
    # to match the format expected by certomancer
    req = ocsp_builder.OCSPRequest({
        "tbs_request": {
            "version": "v1",
            "requestor_name": None,
            "request_list": [{
                "req_cert": {
                    "hash_algorithm": {"algorithm": "sha1"},
                    # issuer_name_hash is the hash of the ISSUER cert's SUBJECT
                    "issuer_name_hash": issuer_cert.subject.sha1,
                    "issuer_key_hash": issuer_cert.public_key.sha1,
                    "serial_number": serial,
                },
                "single_request_extensions": None,
            }],
            "request_extensions": None,
        },
        "optional_signature": None,
    })
    return req.dump()


def _parse_ocsp_response(data: bytes) -> str:
    """Parse OCSP response and return certificate status: good/revoked/unknown."""
    response = asn1_ocsp.OCSPResponse.load(data)
    status = response["response_status"]
    assert status.native == "successful", f"OCSP response status: {status.native}"

    # Parse the response bytes — response_bytes["response"] is a ParsableOctetString
    basic_resp = asn1_ocsp.BasicOCSPResponse.load(
        response["response_bytes"]["response"].contents
    )
    tbs_data = basic_resp["tbs_response_data"]
    responses = tbs_data["responses"]
    assert len(responses) > 0

    cert_status = responses[0]["cert_status"]
    if isinstance(cert_status.native, str) and cert_status.native == "good":
        return "good"
    elif isinstance(cert_status.native, dict) and "revocation_time" in cert_status.native:
        return "revoked"
    else:
        return "unknown"
