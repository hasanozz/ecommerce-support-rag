from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.config import Settings, _resolve_secrets_file
from backend.app.services.gemini import GeminiService


def valid_settings(**overrides) -> dict:
    values = {
        "google_client_id": "test-client-id",
        "google_client_secret": "test-client-secret",
        "google_redirect_uri": "http://localhost:8000/auth/google/callback",
        "gemini_api_key": "test-api-key",
        "gemini_model": "gemini-default",
        "gemini_model_dev": "gemini-development",
        "session_secret": "s" * 32,
        "ip_hash_secret": "i" * 32,
        "admin_emails": ["[admin@example.com](mailto:admin@example.com)"],
    }
    values.update(overrides)
    return values


def test_rejects_short_session_secret():
    with pytest.raises(ValidationError):
        Settings(**valid_settings(session_secret="too-short"))


def test_secrets_file_environment_variable_is_required(monkeypatch):
    monkeypatch.delenv("SECRETS_FILE", raising=False)
    with pytest.raises(RuntimeError, match="SECRETS_FILE environment variable"):
        _resolve_secrets_file()


def test_normalizes_markdown_admin_email():
    settings = Settings(**valid_settings())
    assert settings.admin_emails == ["admin@example.com"]


def test_gemini_model_selection():
    service = GeminiService(Settings(**valid_settings()))
    assert service.model_name() == "gemini-default"
    assert service.model_name(use_dev_model=True) == "gemini-development"
    assert service.settings.gemini_max_retries == 2
