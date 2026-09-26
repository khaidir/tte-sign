"""Public configuration endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["config"])


class ServerSignerInfo(BaseModel):
    available: bool = False
    common_name: str = ""
    not_after: str = ""


class PublicConfig(BaseModel):
    version: str = "1.0.0"
    auth_mode: str = "none"
    max_upload_mb: int = 20
    max_pages: int = 200
    max_image_mb: int = 2
    doc_ttl_minutes: int = 30
    pades_levels: list[str] = ["B-B", "B-T", "B-LT", "B-LTA"]
    default_level: str = "B-T"
    tsa_configured: bool = False
    online_validation: bool = True
    server_signer: ServerSignerInfo = ServerSignerInfo()
    fonts: list[str] = ["script", "sans", "serif"]
    max_placements: int = 1


@router.get("/config", response_model=PublicConfig)
async def get_config():
    settings = get_settings()
    return PublicConfig(
        version="1.0.0",
        auth_mode=settings.auth_mode.value,
        max_upload_mb=settings.max_upload_mb,
        max_pages=settings.max_pages,
        max_image_mb=settings.max_image_mb,
        doc_ttl_minutes=settings.doc_ttl_minutes,
        pades_levels=[lvl.value for lvl in settings.allowed_levels_list],
        default_level=settings.default_level.value,
        tsa_configured=settings.tsa_configured,
        online_validation=settings.validation_fetch,
        server_signer=ServerSignerInfo(available=settings.server_signer_available),
        fonts=["script", "sans", "serif"],
        max_placements=settings.max_placements,
    )
