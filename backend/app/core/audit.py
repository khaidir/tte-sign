"""Audit logger with hash chain (tamper-evident)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_request_id

_FORBIDDEN_FIELDS = {"passphrase", "pkcs12", "private_key", "content", "image"}

logger = logging.getLogger("tte.audit")


def _canonical_json(obj: dict[str, Any]) -> str:
    """Serialize to canonical JSON (sorted keys, no extra whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class AuditLogger:
    """Audit logger with hash chain.

    Each record is hashed with the previous record's hash to form a chain.
    Sink: stdout (always). File sink can be added later.
    """

    def __init__(self) -> None:
        self._prev_hash = "0" * 64  # Genesis hash

    def emit(self, event: str, **fields: Any) -> dict[str, Any]:
        """Emit an audit event.

        Args:
            event: Event name (e.g. 'document.uploaded').
            **fields: Additional fields. Must not contain forbidden keys.

        Returns:
            The full audit record dict.

        Raises:
            ValueError: If a forbidden field is included.
        """
        for key in fields:
            if key.lower() in _FORBIDDEN_FIELDS:
                msg = f"Field '{key}' is not allowed in audit records"
                raise ValueError(msg)

        ts = (
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{datetime.now(UTC).microsecond:06d}Z"
        )  # noqa: E501
        record: dict[str, Any] = {
            "ts": ts,
            "event": event,
            "request_id": get_request_id(),
        }
        record.update(fields)

        # Build hash chain
        record["prev_hash"] = self._prev_hash
        record_str = _canonical_json(record)
        record_hash = hashlib.sha256(record_str.encode("utf-8")).hexdigest()
        record["hash"] = record_hash
        self._prev_hash = record_hash

        # Emit to stdout
        logger.info(event, extra=record)

        return record

    def verify_chain(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Verify a hash chain of audit records.

        Args:
            records: List of audit record dicts (must include 'prev_hash' and 'hash').

        Returns:
            List of records with a '_chain_valid' field added.
        """
        prev = "0" * 64
        results = []
        for rec in records:
            expected_hash = rec.get("hash", "")
            prev_hash = rec.get("prev_hash", "")

            # Recompute hash
            check = dict(rec)
            check.pop("hash", None)
            check.pop("_chain_valid", None)
            check_str = _canonical_json(check)
            computed = hashlib.sha256(check_str.encode("utf-8")).hexdigest()

            valid = computed == expected_hash and prev_hash == prev
            rec["_chain_valid"] = valid
            results.append(rec)
            if valid:
                prev = expected_hash
            else:
                prev = ""
        return results


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
