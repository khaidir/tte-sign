"""Pydantic schemas for the TTE PDF API (Lampiran A.2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentKind(StrEnum):
    ORIGINAL = "original"
    STAMPED = "stamped"
    SIGNED = "signed"


class PageInfo(BaseModel):
    """Per-page geometry in PDF user space (origin bottom-left, pt)."""

    index: int
    width_pt: float = Field(..., description="CropBox width before rotation")
    height_pt: float = Field(..., description="CropBox height before rotation")
    rotation: int = Field(..., description="Page rotation normalized to 0/90/180/270")
    crop_box: list[float] = Field(
        ..., description="CropBox [x0, y0, x1, y1] in PDF user space"
    )
    media_box: list[float] = Field(
        ..., description="MediaBox [x0, y0, x1, y1] in PDF user space"
    )


class DocumentMeta(BaseModel):
    """Document metadata response (Lampiran A.2)."""

    id: str
    parent_id: str | None = None
    kind: DocumentKind = DocumentKind.ORIGINAL
    filename: str
    size_bytes: int
    sha256: str
    page_count: int
    pdf_version: str | None = None
    pages: list[PageInfo] = []
    has_signatures: bool = False
    signature_count: int = 0
    created_at: str
    expires_at: str
    links: dict[str, str] = Field(default_factory=dict)


class AssetMeta(BaseModel):
    """Asset metadata response (Lampiran A.2)."""

    id: str
    type: str  # image | text | drawn
    mime: str = "image/png"
    width_px: int
    height_px: int
    aspect_ratio: float
    sha256: str
    created_at: str
    expires_at: str
    links: dict[str, str] = Field(default_factory=dict)


class TextAssetRequest(BaseModel):
    """Request body for POST /assets/text."""

    lines: list[str] = Field(..., min_length=1, max_length=3)
    font: str = "script"
    color: str = "#0B1F4B"
    align: str = "center"


class Placement(BaseModel):
    """Placement of an asset on a page (Lampiran A.2)."""

    asset_id: str
    page: int = Field(..., ge=0)
    unit: str = "ratio"  # ratio | pt
    origin: str = "top-left"  # top-left | pdf
    rect: dict[str, float] = Field(
        ...,
        description="For unit=ratio, origin=top-left: {x, y, width, height} in ratio [0,1]",
    )


class StampRequest(BaseModel):
    """Request body for POST /documents/{id}/stamp."""

    placements: list[Placement] = Field(..., min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)


class PadesSignerSource(StrEnum):
    PKCS12 = "pkcs12"
    SERVER = "server"


class PadesMetadata(BaseModel):
    reason: str | None = None
    location: str | None = None
    contact_info: str | None = None
    field_name: str | None = None


class PadesAppearance(BaseModel):
    show_details: bool = True
    details_lang: str = "id"


class PadesConsent(BaseModel):
    accepted: bool = False
    statement_version: str = "2026-09-v1"


class PadesRequest(BaseModel):
    """JSON part of multipart POST /documents/{id}/pades."""

    placement: Placement | None = None
    extra_stamps: list[Placement] = Field(default_factory=list)
    level: str = "B-T"
    signer: dict[str, Any] = Field(default_factory=lambda: {"source": "pkcs12"})
    metadata: PadesMetadata = Field(default_factory=PadesMetadata)
    appearance: PadesAppearance = Field(default_factory=PadesAppearance)
    certify: bool = False
    consent: PadesConsent = Field(default_factory=PadesConsent)


class SignerInfo(BaseModel):
    common_name: str | None = None
    organization: str | None = None
    serial: str | None = None
    issuer: str | None = None
    not_before: str | None = None
    not_after: str | None = None


class TimestampInfo(BaseModel):
    time: str | None = None
    tsa: str | None = None


class SignatureInfo(BaseModel):
    field_name: str
    page: int | None = None
    pdf_rect: list[float] | None = None
    level_applied: str | None = None
    digest_algorithm: str = "sha256"
    signature_algorithm: str | None = None
    signer: SignerInfo = Field(default_factory=SignerInfo)
    signing_time: str | None = None
    timestamp: TimestampInfo = Field(default_factory=TimestampInfo)


class SignResult(BaseModel):
    """Response for POST /documents/{id}/pades."""

    document: DocumentMeta
    signature: SignatureInfo


class PlacementApplied(BaseModel):
    page: int
    pdf_rect: list[float]


class StampResult(BaseModel):
    """Response for POST /documents/{id}/stamp."""

    document: DocumentMeta
    placements_applied: list[PlacementApplied] = []
    warnings: list[str] = []
