"""Tests for error handling."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import (
    AppError,
    ErrorCode,
    register_error_handlers,
)
from app.core.middleware import RequestIDMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/app-error")
    async def app_error():
        raise AppError(ErrorCode.PDF_CORRUPT, detail="File tidak dapat dibaca.")

    @app.get("/validation-error")
    async def validation_error(body: dict):  # type: ignore[arg-type]
        return body  # pragma: no cover

    @app.get("/http-404")
    async def http_404():
        raise HTTPException(404)

    @app.get("/http-405")
    async def http_405():
        raise HTTPException(405)

    @app.get("/internal-error")
    async def internal_error():
        raise RuntimeError("something broke")

    return app


client = TestClient(_make_app(), raise_server_exceptions=False)


class TestAppError:
    def test_app_error_returns_problem_details(self):
        resp = client.get("/app-error")
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "PDF_CORRUPT"
        assert body["title"] == "Berkas PDF rusak atau tidak dapat dibaca"
        assert body["detail"] == "File tidak dapat dibaca."
        assert body["status"] == 422
        assert "request_id" in body
        assert body["instance"] == "/app-error"

    def test_validation_error_no_input_values(self):
        resp = client.get("/validation-error", params={"invalid": 1})
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert "errors" in body
        for err in body["errors"]:
            assert "location" in err
            assert "message" in err
            # Ensure no input values leaked
            assert "invalid" not in str(err)

    def test_http_404(self):
        resp = client.get("/http-404")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "NOT_FOUND"

    def test_http_405(self):
        resp = client.post("/http-405")
        assert resp.status_code == 405
        body = resp.json()
        # Starlette returns 405 as plain JSON, not through our handler
        assert "detail" in body

    def test_internal_error_no_stack_in_response(self):
        resp = client.get("/internal-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "Traceback" not in body["detail"]
        assert "request_id" in body

    def test_x_request_id_present(self):
        resp = client.get("/ok")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"].startswith("req_")

    def test_x_request_id_passthrough(self):
        resp = client.get("/ok", headers={"X-Request-ID": "my-custom-id-123"})
        assert resp.headers["X-Request-ID"] == "my-custom-id-123"

    def test_x_request_id_invalid_rejected(self):
        resp = client.get("/ok", headers={"X-Request-ID": "<script>alert(1)</script>"})
        rid = resp.headers["X-Request-ID"]
        assert rid.startswith("req_")
        assert "<script>" not in rid
