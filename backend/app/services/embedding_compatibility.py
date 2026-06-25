from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import EmbeddingIngest
from .embedding import EmbeddingService


def expected_model_dimension(model_name: str) -> int | None:
    normalized = model_name.casefold()
    if "bge-m3" in normalized:
        return 1024
    return None


def validate_model_dimension(
    settings: Settings, embedding_service: EmbeddingService
) -> int:
    expected = expected_model_dimension(settings.embedding_model)
    if expected is not None and settings.embedding_dimension != expected:
        raise RuntimeError(
            f"{settings.embedding_model} için embedding_dimension {expected} olmalıdır."
        )
    sample = embedding_service.embed_query("embedding boyut kontrolü")
    actual = len(sample)
    if actual != settings.embedding_dimension:
        raise RuntimeError(
            "Embedding model çıktısı ile EMBEDDING_DIMENSION uyuşmuyor: "
            f"model={actual}, config={settings.embedding_dimension}."
        )
    return actual


async def database_vector_dimensions(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            text(
                """
                SELECT c.relname AS table_name,
                       format_type(a.atttypid, a.atttypmod) AS formatted_type
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relname IN ('chunks', 'similar_solutions')
                  AND a.attname = 'embedding'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                """
            )
        )
    ).all()
    dimensions: dict[str, int] = {}
    for table_name, formatted_type in rows:
        match = re.fullmatch(r"vector\((\d+)\)", formatted_type or "")
        if not match:
            raise RuntimeError(f"{table_name}.embedding sabit boyutlu vector değil.")
        dimensions[table_name] = int(match.group(1))
    return dimensions


async def validate_database_dimensions(
    session: AsyncSession, expected_dimension: int
) -> None:
    dimensions = await database_vector_dimensions(session)
    required = {"chunks", "similar_solutions"}
    missing = required.difference(dimensions)
    if missing:
        raise RuntimeError(
            "Embedding kolonları bulunamadı: " + ", ".join(sorted(missing))
        )
    invalid = {
        table: dimension
        for table, dimension in dimensions.items()
        if dimension != expected_dimension
    }
    if invalid:
        details = ", ".join(f"{table}=vector({dim})" for table, dim in invalid.items())
        raise RuntimeError(
            f"PostgreSQL vector boyutu uyuşmuyor; beklenen vector({expected_dimension}), "
            f"mevcut {details}."
        )


async def ensure_active_ingest_compatible(
    session: AsyncSession, settings: Settings
) -> EmbeddingIngest:
    active = await session.scalar(
        select(EmbeddingIngest)
        .where(EmbeddingIngest.is_active.is_(True))
        .order_by(EmbeddingIngest.id.desc())
    )
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Aktif embedding ingest metadata kaydı yok. Ingest işlemini çalıştırın.",
        )
    if (
        active.provider != settings.embedding_provider
        or active.model_name
        != (
            "hashing-sha256-v1"
            if settings.embedding_provider == "hashing"
            else settings.embedding_model
        )
        or active.dimension != settings.embedding_dimension
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Aktif embedding metadata ile çalışan retrieval modeli uyuşmuyor.",
        )
    return active
