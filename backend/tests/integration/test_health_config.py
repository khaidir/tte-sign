"""Integration tests for health and config endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


class TestHealth:
    def test_live(self):
        resp = client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_ready(self):
        resp = client.get("/api/v1/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("ready", "degraded")
        assert "checks" in body
        assert "data_dir" in body["checks"]

    def test_x_request_id_header(self):
        resp = client.get("/api/v1/health/live")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"].startswith("req_")

    def test_x_request_id_passthrough(self):
        resp = client.get("/api/v1/health/live", headers={"X-Request-ID": "my-test-id"})
        assert resp.headers["X-Request-ID"] == "my-test-id"


class TestConfig:
    def test_config_returns_public_info(self):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "1.0.0"
        assert body["auth_mode"] == "none"
        assert body["max_upload_mb"] == 20
        assert body["max_pages"] == 200
        assert "pades_levels" in body
        assert body["default_level"] == "B-T"
        assert "tsa_configured" in body
        assert "server_signer" in body
        assert body["server_signer"]["available"] is False
        assert body["fonts"] == ["script", "sans", "serif"]
        assert body["max_placements"] == 1
