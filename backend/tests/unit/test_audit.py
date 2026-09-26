"""Tests for audit hash chain."""

from __future__ import annotations

import copy

import pytest

from app.core.audit import AuditLogger


class TestAuditLogger:
    def test_emit_returns_record_with_hash(self):
        logger = AuditLogger()
        rec = logger.emit("test.event", document_id="doc_123")
        assert "ts" in rec
        assert rec["event"] == "test.event"
        assert rec["document_id"] == "doc_123"
        assert rec["prev_hash"] == "0" * 64
        assert len(rec["hash"]) == 64

    def test_chain_links(self):
        logger = AuditLogger()
        r1 = logger.emit("event.one")
        r2 = logger.emit("event.two")
        assert r1["hash"] == r2["prev_hash"]
        assert r1["hash"] != r2["hash"]

    def test_verify_valid_chain(self):
        logger = AuditLogger()
        records = [
            logger.emit("event.one", data="a"),
            logger.emit("event.two", data="b"),
            logger.emit("event.three", data="c"),
        ]
        results = logger.verify_chain(records)
        assert all(r["_chain_valid"] for r in results)

    def test_verify_tampered_record(self):
        logger = AuditLogger()
        records = [
            logger.emit("event.one", data="a"),
            logger.emit("event.two", data="b"),
            logger.emit("event.three", data="c"),
        ]
        # Tamper with the middle record
        tampered = copy.deepcopy(records)
        tampered[1]["data"] = "modified"
        results = logger.verify_chain(tampered)
        assert results[0]["_chain_valid"] is True
        assert results[1]["_chain_valid"] is False
        # Third record chain is broken because prev_hash doesn't match
        assert results[2]["_chain_valid"] is False

    def test_forbidden_fields_raise(self):
        logger = AuditLogger()
        with pytest.raises(ValueError, match="passphrase"):
            logger.emit("test.event", passphrase="secret")
        with pytest.raises(ValueError, match="pkcs12"):
            logger.emit("test.event", pkcs12=b"data")
        with pytest.raises(ValueError, match="private_key"):
            logger.emit("test.event", private_key="key")
        with pytest.raises(ValueError, match="content"):
            logger.emit("test.event", content="pdf")
        with pytest.raises(ValueError, match="image"):
            logger.emit("test.event", image="img")
