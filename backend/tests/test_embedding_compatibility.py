import pytest

from backend.app.config import Settings
from backend.app.services.embedding_compatibility import expected_model_dimension


def test_bge_m3_requires_1024_dimensions():
    assert expected_model_dimension("BAAI/bge-m3") == 1024


def test_classifier_provider_defaults_to_rule_based():
    settings = Settings(
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:8000/auth/google/callback",
        gemini_api_key="test-api-key",
        gemini_model="gemini-test",
        gemini_model_dev="gemini-test-dev",
        session_secret="s" * 32,
        ip_hash_secret="i" * 32,
    )
    assert settings.classifier_provider == "rule_based"
    assert settings.embedding_provider == "hashing"
    assert settings.embedding_model == "hashing-sha256-v1"
    assert settings.hashing_min_retrieval_score == 0.30
