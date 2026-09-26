"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])

# Registry of readiness checks
_ready_checks: dict[str, callable] = {}


def register_ready_check(name: str, check_fn: callable) -> None:
    _ready_checks[name] = check_fn


@router.get("/live")
async def health_live():
    return {"status": "ok"}


@router.get("/ready")
async def health_ready():
    checks = {}
    all_ok = True
    for name, fn in _ready_checks.items():
        try:
            result = fn()
            checks[name] = result
            if result.get("status") != "ok":
                all_ok = False
        except Exception as e:
            checks[name] = {"status": "error", "detail": str(e)}
            all_ok = False
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
