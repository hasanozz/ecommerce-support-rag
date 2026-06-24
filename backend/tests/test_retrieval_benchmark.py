import pytest

from backend.scripts.retrieval_benchmark import (
    validate_benchmark_embedding_config,
)


def test_benchmark_accepts_bge_m3_config():
    validate_benchmark_embedding_config(
        "sentence_transformers", "BAAI/bge-m3", 1024
    )


@pytest.mark.parametrize(
    ("provider", "model", "dimension"),
    [
        ("hashing", "hashing-sha256-v1", 1024),
        ("sentence_transformers", "intfloat/multilingual-e5-large", 1024),
        ("sentence_transformers", "BAAI/bge-m3", 768),
    ],
)
def test_benchmark_rejects_unexpected_embedding_config(
    provider: str, model: str, dimension: int
):
    with pytest.raises(RuntimeError) as exc_info:
        validate_benchmark_embedding_config(provider, model, dimension)

    message = str(exc_info.value)
    assert f"provider={provider}" in message
    assert f"model={model}" in message
    assert f"dimension={dimension}" in message
