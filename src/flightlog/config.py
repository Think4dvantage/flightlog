"""
Configuration loading and validation.

The whole app reads config through `get_config()` — never `os.environ` directly. The only
environment variable this module honours is `CONFIG_PATH`, which points at the YAML file.

`_config` is a module-level singleton. Tests monkeypatch it directly, which bypasses all
file I/O at every call site — see .ai/instructions/06-testing-conventions.md.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.yml"

# A JWT secret matching any of these means someone shipped the example file.
# Startup refuses to continue — see AuthConfig.validate_secret.
PLACEHOLDER_SECRETS = frozenset(
    {
        "change-me",
        "changeme",
        "secret",
        "your-secret-here",
        "replace-with-openssl-rand-hex-32",
        "CHANGE_ME_openssl_rand_hex_32",
    }
)

MIN_JWT_SECRET_LENGTH = 32


class DatabaseConfig(BaseModel):
    path: str = "data/flightlog.db"


class AuthConfig(BaseModel):
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # The "private now, public-ready later" gate. The register endpoint, its schemas,
    # hashing and the token pair all exist and are tested — only this flag is off.
    allow_self_registration: bool = False

    # Used once, by _seed_bootstrap_admin, and skipped if any user already exists.
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    def validate_secret(self) -> None:
        """
        Fail closed. A dev placeholder reaching production is a total auth bypass, so this
        raises rather than warning. Called from the lifespan, not from the validator, so
        that tests can construct a config without tripping it.
        """
        if not self.jwt_secret:
            raise RuntimeError("auth.jwt_secret is not set — refusing to start")
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise RuntimeError(
                f"auth.jwt_secret is shorter than {MIN_JWT_SECRET_LENGTH} characters "
                "— refusing to start"
            )
        if self.jwt_secret in PLACEHOLDER_SECRETS:
            raise RuntimeError("auth.jwt_secret is a known placeholder value — refusing to start")


class StorageConfig(BaseModel):
    igc_dir: str = "data/igc"
    max_igc_bytes: int = 5 * 1024 * 1024
    max_import_bytes: int = 5 * 1024 * 1024


class SitesConfig(BaseModel):
    # Two sites closer than this are treated as the same place on creation.
    dedup_radius_m: float = 250.0
    allow_user_sites: bool = True


class IgcParsingConfig(BaseModel):
    """Mirrors libigc.FlightParsingConfig's thermal-detection parameters — the exact three
    names and defaults confirmed against the installed 1.2.0 package (specs/003-igc-ingest-
    analysis/research.md). libigc has no separate glide-tuning parameter; a glide is simply
    the gap between two thermals, so there is nothing more to expose here."""

    min_bearing_change_circling: float = 6.0
    min_time_for_bearing_change: float = 5.0
    min_time_for_thermal: float = 60.0


class IgcConfig(BaseModel):
    parsing: IgcParsingConfig = Field(default_factory=IgcParsingConfig)


class LoggingConfig(BaseModel):
    level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    file: str = ""


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    # slowapi rate-string syntax ("<n>/<second|minute|hour|day>"). Applies only to
    # /api/public/* (v0.9) — the authenticated surface is never limited by this.
    public_rate_limit: str = "30/minute"


class MainConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    sites: SitesConfig = Field(default_factory=SitesConfig)
    igc: IgcConfig = Field(default_factory=IgcConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    @field_validator("logging", mode="before")
    @classmethod
    def _lowercase_level(cls, v):
        if isinstance(v, dict) and isinstance(v.get("level"), str):
            v = {**v, "level": v["level"].lower()}
        return v


_config: MainConfig | None = None
_config_source: str = "<defaults>"


def load_config(path: str | Path | None = None) -> MainConfig:
    """Read and validate the YAML config. Missing file falls back to defaults."""
    global _config, _config_source

    resolved = Path(path or os.environ.get("CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    if resolved.is_file():
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        _config_source = str(resolved)
    else:
        raw = {}
        _config_source = f"<defaults — {resolved} not found>"

    _config = MainConfig(**raw)
    return _config


def get_config() -> MainConfig:
    if _config is None:
        return load_config()
    return _config


def get_config_source() -> str:
    return _config_source


def log_effective_config(cfg: MainConfig) -> None:
    """
    Log every resolved non-secret value at INFO.

    Per .ai/instructions/08-operability.md an operator must be able to reconstruct the
    running configuration from cold logs. Secrets are reported as a boolean only.
    """
    logger.info("Config source: %s", get_config_source())
    logger.info("Config database.path=%s", cfg.database.path)
    logger.info("Config storage.igc_dir=%s", cfg.storage.igc_dir)
    logger.info("Config storage.max_igc_bytes=%d", cfg.storage.max_igc_bytes)
    logger.info("Config storage.max_import_bytes=%d", cfg.storage.max_import_bytes)
    logger.info("Config sites.dedup_radius_m=%.1f", cfg.sites.dedup_radius_m)
    logger.info(
        "Config igc.parsing.min_bearing_change_circling=%.1f "
        "min_time_for_bearing_change=%.1f min_time_for_thermal=%.1f",
        cfg.igc.parsing.min_bearing_change_circling,
        cfg.igc.parsing.min_time_for_bearing_change,
        cfg.igc.parsing.min_time_for_thermal,
    )
    logger.info("Config auth.jwt_algorithm=%s", cfg.auth.jwt_algorithm)
    logger.info(
        "Config auth.access_token_expire_minutes=%d refresh_token_expire_days=%d",
        cfg.auth.access_token_expire_minutes,
        cfg.auth.refresh_token_expire_days,
    )
    logger.info("Config auth.allow_self_registration=%s", cfg.auth.allow_self_registration)
    logger.info("Config auth.jwt_secret set=%s", bool(cfg.auth.jwt_secret))
    logger.info(
        "Config logging.level=%s file=%s", cfg.logging.level, cfg.logging.file or "<stdout>"
    )
    logger.info("Config api.host=%s port=%d", cfg.api.host, cfg.api.port)
    logger.info("Config api.public_rate_limit=%s", cfg.api.public_rate_limit)
