import pytest

from backend.app.config import Settings
from backend.app.services.classifier import ClassifierService
from backend.app.services.confidence import composite_confidence


def settings(**overrides):
    values = {
        "google_client_id": "test-client-id",
        "google_client_secret": "test-client-secret",
        "google_redirect_uri": "http://localhost:8000/auth/google/callback",
        "gemini_api_key": "test-api-key",
        "gemini_model": "gemini-test",
        "gemini_model_dev": "gemini-test-dev",
        "session_secret": "s" * 32,
        "ip_hash_secret": "i" * 32,
    }
    values.update(overrides)
    return Settings(**values)


def test_confidence_with_reranker():
    assert composite_confidence(0.8, 0.9, 0.7) == 0.81


def test_confidence_without_reranker():
    assert composite_confidence(0.8, None, 0.7) == 0.77


def test_confidence_is_none_without_classifier_score():
    assert composite_confidence(0.8, 0.9, None) is None


@pytest.mark.asyncio
async def test_qwen_stub_falls_back_to_rule_based():
    config = settings(classifier_provider="qwen")
    result = await ClassifierService(config).classify(
        "Kartımdan para çekildi", "Kartımdan para çekildi"
    )
    assert result.provider == "rule_based"
    assert result.category == "ODEME"
    assert result.priority == "HIGH"
