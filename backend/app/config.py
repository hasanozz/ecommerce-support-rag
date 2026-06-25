from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "DestekAI RAG API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://localhost:5500"]
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/destekai"
    )
    db_echo: bool = False
    auto_create_tables: bool = True

    session_cookie_name: str = "destekai_session"
    session_ttl_hours: int = 168
    session_secret: SecretStr
    ip_hash_secret: SecretStr
    admin_emails: list[str] = Field(default_factory=list)

    google_client_id: str
    google_client_secret: SecretStr
    google_redirect_uri: str

    embedding_provider: str = "hashing"
    embedding_model: str = "hashing-sha256-v1"
    embedding_dimension: int = 1024
    embedding_device: str = "cpu"
    embedding_ingest_version: str = "1"

    search_limit: int = 10
    min_retrieval_score: float = 0.55
    hashing_min_retrieval_score: float = 0.30
    confidence_high_threshold: float = 0.78
    confidence_medium_threshold: float = 0.62

    llm_provider: str = "gemini"
    gemini_api_key: SecretStr
    gemini_model: str
    gemini_model_dev: str
    llm_timeout_seconds: int = 60
    gemini_max_retries: int = 2
    gemini_retry_base_seconds: float = 1.0
    gemini_prompt_cost_per_million: float | None = None
    gemini_completion_cost_per_million: float | None = None

    classifier_provider: str = "rule_based"
    classifier_fallback_provider: str = "rule_based"

    similar_solution_min_views: int = 10
    similar_solution_min_helpful: int = 5
    similar_solution_min_success_rate: float = 0.8

    max_query_length: int = 1000
    max_ticket_note_length: int = 1000
    chat_rate_limit: int = 20
    chat_rate_window_seconds: int = 600
    feedback_rate_limit: int = 30
    feedback_rate_window_seconds: int = 3600
    ticket_daily_limit: int = 5

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    processed_data_path: Path = PROJECT_ROOT / "data" / "processed"
    rag_documents_final_path: Path = PROJECT_ROOT / "rag_documents_final"
    rag_chunks_clean_path: Path = PROJECT_ROOT / "rag_chunks" / "rag_chunks_clean.jsonl"
    frontend_path: Path = PROJECT_ROOT / "frontend"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            normalized = []
            for item in value:
                text = str(item).strip()
                markdown_match = re.fullmatch(
                    r"\[([^\]]+)\]\(mailto:[^)]+\)", text, flags=re.IGNORECASE
                )
                normalized.append(
                    (markdown_match.group(1) if markdown_match else text).casefold()
                )
            return normalized
        return value

    @model_validator(mode="after")
    def validate_required_secrets(self) -> "Settings":
        required_strings = {
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_REDIRECT_URI": self.google_redirect_uri,
            "GEMINI_MODEL": self.gemini_model,
            "GEMINI_MODEL_DEV": self.gemini_model_dev,
        }
        required_secrets = {
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "GEMINI_API_KEY": self.gemini_api_key,
            "SESSION_SECRET": self.session_secret,
            "IP_HASH_SECRET": self.ip_hash_secret,
        }
        missing = [
            name for name, value in required_strings.items() if not value.strip()
        ]
        missing.extend(
            name
            for name, value in required_secrets.items()
            if not value.get_secret_value().strip()
        )
        if missing:
            raise ValueError("Zorunlu config değerleri eksik: " + ", ".join(missing))
        short_secrets = [
            name
            for name, value in {
                "SESSION_SECRET": self.session_secret,
                "IP_HASH_SECRET": self.ip_hash_secret,
            }.items()
            if len(value.get_secret_value()) < 32
        ]
        if short_secrets:
            raise ValueError(
                "En az 32 karakter olması gereken secretlar: "
                + ", ".join(short_secrets)
            )
        return self


def _resolve_secrets_file() -> Path:
    secrets_file = os.getenv("SECRETS_FILE", "").strip()
    if not secrets_file:
        raise RuntimeError(
            "SECRETS_FILE environment variable tanımlı değil. "
            "Repo dışındaki .env.local dosyasının mutlak yolunu belirtin."
        )
    path = Path(secrets_file).expanduser()
    if not path.is_absolute():
        raise RuntimeError("SECRETS_FILE mutlak bir repo dışı yol olmalıdır.")
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise RuntimeError("SECRETS_FILE proje dizini içinde olamaz.")
    if not resolved.is_file():
        raise RuntimeError("SECRETS_FILE ile belirtilen secret dosyası bulunamadı.")
    return resolved


@lru_cache
def get_settings() -> Settings:
    path = _resolve_secrets_file()
    return Settings(_env_file=path, _env_file_encoding="utf-8")
