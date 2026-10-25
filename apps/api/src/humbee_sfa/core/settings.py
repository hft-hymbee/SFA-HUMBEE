"""Application settings loaded from YAML defaults plus secret environment values."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote, urlencode, urlparse

import yaml  # type: ignore[import-untyped]
from pydantic import Field, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _api_root() -> Path:
    installed = Path(__file__).resolve().parents[3]
    if (installed / "config" / "application.yml").exists():
        return installed
    cwd = Path.cwd()
    if (cwd / "config" / "application.yml").exists():
        return cwd
    return installed


API_ROOT = _api_root()
CONFIG_DIR = API_ROOT / "config"
ENV_FILE = API_ROOT / ".env"
PROFILE_PATTERN = re.compile(r"^[a-z0-9_-]+$")
ENV_PREFIX = "HUMBEE_SFA_"
SECRETS_JSON_ENV = f"{ENV_PREFIX}SECRETS_JSON"


def _selected_profile() -> str:
    profile = os.getenv("HUMBEE_SFA_PROFILE", "local").strip() or "local"
    if not PROFILE_PATTERN.fullmatch(profile):
        raise RuntimeError("HUMBEE_SFA_PROFILE may contain only lowercase letters, digits, '-' or '_'")
    return profile


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a YAML mapping at the top level")
    return data


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Load non-secret settings from application.yml and application-{profile}.yml."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        profile = _selected_profile()
        config = _read_yaml_mapping(CONFIG_DIR / "application.yml")
        config.update(_read_yaml_mapping(CONFIG_DIR / f"application-{profile}.yml"))
        config.setdefault("profile", profile)
        return config


class SecretsJsonSettingsSource(PydanticBaseSettingsSource):
    """Load settings from one JSON object in HUMBEE_SFA_SECRETS_JSON.

    ECS injects the whole Secrets Manager secret into that variable. Its keys are the same names as
    the individual environment variables (HUMBEE_SFA_JWT_SECRET, HUMBEE_API_KEY, ...); an individual
    environment variable still wins over the JSON.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        raw = os.getenv(SECRETS_JSON_ENV, "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Never echo the payload: it holds secrets.
            raise ValueError(f"{SECRETS_JSON_ENV} must be a JSON object") from None
        if not isinstance(data, dict):
            raise TypeError(f"{SECRETS_JSON_ENV} must be a JSON object")

        by_env_name = {str(key).upper(): value for key, value in data.items()}
        values: dict[str, Any] = {}
        known: set[str] = set()
        for field_name, field in self.settings_cls.model_fields.items():
            alias = field.validation_alias if isinstance(field.validation_alias, str) else None
            env_name = alias or f"{ENV_PREFIX}{field_name.upper()}"
            known.add(env_name)
            if env_name not in by_env_name:
                continue
            value = by_env_name[env_name]
            if isinstance(value, str) and self.field_is_complex(field):
                value = self.decode_complex_value(field_name, field, value)
            values[alias or field_name] = value

        unknown = sorted(set(by_env_name) - known)
        if unknown:
            # A misspelt key would otherwise be dropped silently.
            raise ValueError(f"{SECRETS_JSON_ENV} has unknown keys: {', '.join(unknown)}")
        return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Humbee SFA API"
    profile: str = "local"
    environment: str = "local"
    debug: bool = False
    api_docs_enabled: bool = False
    cors_app_origins: list[str] = Field(default_factory=list)
    cors_web_origins: list[str] = Field(default_factory=list)
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    database_url: str = ""
    db_driver: str = "postgresql+psycopg"
    db_host: str | None = None
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_sslmode: str | None = None
    day_boundary_hour_ist: int = Field(default=0, ge=0, le=23)
    leave_default_yearly_privileged_days: int = Field(default=12, ge=0)
    leave_default_yearly_casual_days: int = Field(default=6, ge=0)
    leave_default_yearly_sick_days: int = Field(default=6, ge=0)
    tenant_id: str
    otp_length: int = Field(ge=4, le=8)
    otp_ttl_seconds: int = Field(ge=30)
    otp_resend_cooldown_seconds: int = Field(ge=0)
    otp_max_attempts: int = Field(ge=1, le=10)
    otp_rate_limit_per_phone_per_hour: int = Field(ge=1)
    otp_rate_limit_per_ip_per_hour: int = Field(ge=1)
    otp_verify_rate_limit_per_challenge: int = Field(default=10, ge=1)
    otp_skip_verification: bool = False
    local_otp_override: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    otp_sms_gateway_url: str = ""
    otp_sms_username: str | None = None
    otp_sms_api_key: str | None = None
    otp_sms_signature: str = "HUMBEE"
    otp_sms_msg_type: str = "PM"
    otp_sms_entity_id: str = ""
    otp_sms_template_id: str = ""
    otp_sms_message_template: str = (
        "Dear Partner, Your OTP to log in to HUMBEE is {otp}. "
        "This code is valid for 5 minutes only. HUMBEE"
    )
    otp_sms_timeout_seconds: float = Field(default=5.0, gt=0)
    otp_request_idempotency_ttl_seconds: int = Field(default=1800, ge=1)
    otp_verify_idempotency_ttl_seconds: int = Field(default=1800, ge=1)
    refresh_idempotency_ttl_seconds: int = Field(default=3600, ge=1)
    access_token_ttl_seconds: int = Field(ge=60)
    refresh_token_ttl_seconds: int = Field(ge=300)
    jwt_secret: str
    jwt_algorithm: str
    phone_hmac_secret: str
    phone_enc_key: str
    # Informational late-punch-in threshold, runtime config not a constant.
    attendance_late_threshold_hour_ist: int = Field(default=9, ge=0, le=23)
    route_sweep_grace_minutes: int = Field(default=5, ge=0)
    # Reporting projector drain cadence — deliberately per-environment:
    # sbx wants fast feedback while verifying producers against live traffic, prod wants a low
    # steady drumbeat. See `ReportingProjectorWorker`.
    reporting_projector_interval_seconds: float = Field(default=21600.0, gt=0)
    # Events older than this many IST business days are quarantined
    # (`beyond_lateness_window`) instead of rewriting an old month. Per-environment so sbx
    # can catch a longer backlog than prod. See `reporting.projector.process_stream`.
    reporting_projector_lateness_window_days: int = Field(default=30, ge=1)
    # The outbox-drain worker polling cadence and batch size.
    outbox_drain_interval_seconds: float = Field(default=5.0, gt=0)
    outbox_drain_batch_size: int = Field(default=20, ge=1)
    humbee_base_url: str = ""
    # Never sourced from YAML or a committed file — bare env var, no HUMBEE_SFA_ prefix.
    # validation_alias makes pydantic-settings read it verbatim, bypassing env_prefix.
    humbee_api_key: str | None = Field(default=None, validation_alias="HUMBEE_API_KEY")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            SecretsJsonSettingsSource(settings_cls),
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def validate_database_url(self) -> Self:
        self.database_url = self.database_url.strip()
        if self.database_url:
            return self

        missing: list[str] = []
        db_host = (self.db_host or "").strip()
        db_name = (self.db_name or "").strip()
        db_user = (self.db_user or "").strip()
        db_password = self.db_password or ""
        if not db_host:
            missing.append("db_host")
        if not db_name:
            missing.append("db_name")
        if not db_user:
            missing.append("db_user")
        if not db_password:
            missing.append("db_password")
        if missing:
            raise ValueError(
                "database_url is required unless all of db_host, db_name, db_user, and "
                f"db_password are provided (missing: {', '.join(missing)})."
            )

        query: dict[str, str] = {}
        if self.db_sslmode and self.db_sslmode.strip():
            query["sslmode"] = self.db_sslmode.strip()

        auth = f"{quote(db_user, safe='')}:{quote(db_password, safe='')}"
        base = f"{self.db_driver}://{auth}@{db_host}:{self.db_port}/{db_name}"
        self.database_url = f"{base}?{urlencode(query)}" if query else base
        return self

    @model_validator(mode="after")
    def validate_local_otp_override(self) -> Self:
        if self.local_otp_override is None:
            return self
        if self.environment not in {"local", "sbx", "test"}:
            raise ValueError("local_otp_override is allowed only in local, sbx, or test environments")
        if len(self.local_otp_override) != self.otp_length:
            raise ValueError("local_otp_override length must match otp_length")
        return self

    @model_validator(mode="after")
    def validate_otp_skip_verification(self) -> Self:
        if self.otp_skip_verification and self.environment not in {"sbx", "test"}:
            raise ValueError("otp_skip_verification is allowed only in sbx or test environments")
        return self

    @model_validator(mode="after")
    def validate_cors_web_origins(self) -> Self:
        if self.environment in {"sbx", "prd"} and not self.cors_web_origins:
            raise ValueError("cors_web_origins must list the web app origin in sbx and prd")
        return self

    @model_validator(mode="after")
    def validate_otp_sms_template(self) -> Self:
        if "{otp}" not in self.otp_sms_message_template:
            raise ValueError("otp_sms_message_template must contain '{otp}' placeholder")
        return self

    @model_validator(mode="after")
    def validate_humbee_config(self) -> Self:
        base_url = self.humbee_base_url.strip().rstrip("/")
        api_key = (self.humbee_api_key or "").strip()
        if not base_url:
            raise ValueError("humbee_base_url is required for Humbee integration.")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("humbee_base_url must be an absolute http(s) URL.")
        if self.environment not in {"local", "test"} and parsed.scheme != "https":
            raise ValueError("humbee_base_url must use https outside local/test environments.")
        if not api_key:
            raise ValueError("HUMBEE_API_KEY is required for Humbee integration.")
        self.humbee_base_url = base_url
        self.humbee_api_key = api_key
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # YAML holds non-secrets; .env or the process environment supplies secrets.
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    get_settings.cache_clear()
