from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
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

    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_device: str = "cpu"

    search_limit: int = 10
    min_retrieval_score: float = 0.55

    llm_provider: str = "disabled"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    llm_timeout_seconds: int = 60

    max_query_length: int = 1000
    processed_data_path: Path = PROJECT_ROOT / "data" / "processed"
    frontend_path: Path = PROJECT_ROOT / "frontend"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
