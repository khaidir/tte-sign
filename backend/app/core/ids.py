"""ID generators: doc_, ast_, req_ prefixed ULID-like IDs."""

from __future__ import annotations

import secrets
import time

_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_BASE32_LEN = len(_BASE32)


def _ulidish(prefix: str) -> str:
    """Generate a 26-char base32 Crockford ID with timestamp prefix ala ULID.

    Format: <prefix>_<10 chars timestamp ms><16 chars random>
    Total: prefix + 1 + 26 = ~30 chars.
    """
    ts = int(time.time() * 1000)
    ts_chars = []
    for _ in range(10):
        ts_chars.append(_BASE32[ts % _BASE32_LEN])
        ts //= _BASE32_LEN
    ts_part = "".join(reversed(ts_chars))

    rand_bytes = secrets.token_bytes(16)
    rand_val = int.from_bytes(rand_bytes, "big")
    rand_chars = []
    for _ in range(16):
        rand_chars.append(_BASE32[rand_val % _BASE32_LEN])
        rand_val //= _BASE32_LEN
    rand_part = "".join(rand_chars)

    return f"{prefix}_{ts_part}{rand_part}"


def new_document_id() -> str:
    return _ulidish("doc")


def new_asset_id() -> str:
    return _ulidish("ast")


def new_request_id() -> str:
    return _ulidish("req")
