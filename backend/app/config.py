from __future__ import annotations

import enum
import re
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PadesLevel(enum.StrEnum):
    B_B = "B-B"
    B_T = "B-T"
    B_LT = "B-LT"
    B_LTA = "B-LTA"


class AuthMode(enum.StrEnum):
    NONE = "none"
    APIKEY = "apikey"
    PROXY = "proxy"


class StampEngine(enum.StrEnum):
    PYMUPDF = "pymupdf"
    PYPDF = "pypdf"


def _read_file(path: str | None) -> str | None:
    """Read a value from a file, used for *_FILE env vars."""
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return p.read_text("utf-8").strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TTE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Server ──────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8080
    web_concurrency: int = Field(default=1, ge=1)
    forwarded_allow_ips: str = "127.0.0.1"
    allowed_hosts: str = ""

    # ── PDF Workers ─────────────────────────────────────────────────────────
    pdf_workers: int = Field(default=2, ge=1)
    job_timeout_seconds: int = Field(default=30, ge=5)
    worker_memory_mb: int = Field(default=768, ge=128)

    # ── Stamp Engine ────────────────────────────────────────────────────────
    stamp_engine: StampEngine = StampEngine.PYMUPDF

    # ── Document Limits ─────────────────────────────────────────────────────
    max_upload_mb: int = Field(default=20, ge=1, le=200)
    max_pages: int = Field(default=200, ge=1, le=5000)
    max_image_mb: int = Field(default=2, ge=1, le=50)
    max_placements: int = Field(default=1, ge=1, le=100)
    default_margin_pt: float = Field(default=36.0, ge=0)

    # ── Storage ─────────────────────────────────────────────────────────────
    data_dir: str = "/data"
    doc_ttl_minutes: int = Field(default=30, ge=1)
    delete_after_download: bool = False

    # ── Auth ────────────────────────────────────────────────────────────────
    auth_mode: AuthMode = AuthMode.NONE
    api_keys_file: str = ""
    proxy_user_header: str = "X-Forwarded-User"
    proxy_trusted_ips: str = ""

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_origins: str = ""

    # ── PAdES ───────────────────────────────────────────────────────────────
    default_level: PadesLevel = PadesLevel.B_T
    allowed_levels: str = "B-B,B-T,B-LT,B-LTA"

    # ── TSA ─────────────────────────────────────────────────────────────────
    tsa_url: str = ""
    tsa_auth_file: str = ""
    tsa_url_fallback: str = ""

    # ── Trust Store ─────────────────────────────────────────────────────────
    trust_dir: str = "/etc/tte/trust"
    trust_system: bool = False
    validation_fetch: bool = True

    # ── Server Signer ───────────────────────────────────────────────────────
    server_signer_p12_file: str = ""
    server_signer_passphrase_file: str = ""

    # ── Audit ───────────────────────────────────────────────────────────────
    audit_file: str = ""

    # ── Logging ─────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── API Docs ────────────────────────────────────────────────────────────
    api_docs_enabled: bool = True

    # ── Security ────────────────────────────────────────────────────────────
    hsts: bool = False

    # ── Rate Limits ─────────────────────────────────────────────────────────
    rate_limit_upload: int = Field(default=30, ge=1)
    rate_limit_pades: int = Field(default=10, ge=1)
    rate_limit_verify: int = Field(default=30, ge=1)
    rate_limit_passphrase: int = Field(default=5, ge=1)

    # ── Storage Key (encryption at rest, Should) ────────────────────────────
    storage_key_file: str = ""

    # ── Computed ────────────────────────────────────────────────────────────

    @property
    def allowed_levels_list(self) -> list[PadesLevel]:
        return self._parsed_allowed_levels

    @property
    def tsa_configured(self) -> bool:
        return bool(self.tsa_url)

    @property
    def server_signer_available(self) -> bool:
        return bool(self.server_signer_p12_file)

    @property
    def server_signer_passphrase(self) -> str | None:
        return _read_file(self.server_signer_passphrase_file)

    @property
    def tsa_auth(self) -> str | None:
        return _read_file(self.tsa_auth_file)

    @property
    def storage_key(self) -> str | None:
        return _read_file(self.storage_key_file)

    # ── Validators ──────────────────────────────────────────────────────────

    _parsed_allowed_levels: list[PadesLevel] = []

    @field_validator("allowed_levels")
    @classmethod
    def _parse_allowed_levels(cls, v: str) -> str:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        for p in parts:
            if p not in PadesLevel._value2member_map_:
                msg = f"Invalid PAdES level: {p}"
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _store_parsed_levels(self) -> Settings:
        parts = [p.strip() for p in self.allowed_levels.split(",") if p.strip()]
        self._parsed_allowed_levels = [PadesLevel(p) for p in parts]
        if self.default_level not in self._parsed_allowed_levels:
            msg = f"default_level {self.default_level} must be in allowed_levels"
            raise ValueError(msg)
        return self

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            msg = f"Invalid log level: {v}"
            raise ValueError(msg)
        return v.upper()

    @field_validator("forwarded_allow_ips")
    @classmethod
    def _validate_forwarded_allow_ips(cls, v: str) -> str:
        if v == "*":
            return v
        parts = v.split(",")
        for p in parts:
            p = p.strip()
            if p and not re.match(r"^[\d.]+$", p):
                msg = f"Invalid IP in forwarded_allow_ips: {p}"
                raise ValueError(msg)
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
