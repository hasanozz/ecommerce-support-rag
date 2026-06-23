from __future__ import annotations

import asyncio
import hashlib
import math

from sqlalchemy import func, select, update

from backend.app.config import get_settings
from backend.app.database import SessionLocal, close_database
from backend.app.models import Chunk, Document, EmbeddingIngest
from backend.app.services.embedding import get_embedding_service
from backend.app.services.embedding_compatibility import validate_database_dimensions


async def main() -> None:
    settings = get_settings()
    embedding = get_embedding_service()
    if settings.embedding_provider != "hashing":
        raise RuntimeError(
            "Legacy bootstrap yalnız doğrulanabilen hashing embeddingleri için çalışır."
        )

    async with SessionLocal() as session:
        samples = (
            await session.scalars(select(Chunk).order_by(Chunk.chunk_id).limit(5))
        ).all()
        if not samples:
            raise RuntimeError("Doğrulanacak chunk bulunamadı.")
        await validate_database_dimensions(session, settings.embedding_dimension)

        for sample in samples:
            stored = list(sample.embedding)
            expected = embedding._hash_embedding(sample.contextual_content)
            dot = sum(a * b for a, b in zip(stored, expected, strict=True))
            stored_norm = math.sqrt(sum(value * value for value in stored)) or 1.0
            expected_norm = math.sqrt(sum(value * value for value in expected)) or 1.0
            similarity = dot / (stored_norm * expected_norm)
            if similarity < 0.99999:
                raise RuntimeError(
                    "Mevcut embeddingler hashing-sha256-v1 ile eşleşmiyor; "
                    "normal ingest çalıştırılmalıdır."
                )

        document_count = int(
            await session.scalar(select(func.count()).select_from(Document)) or 0
        )
        chunk_count = int(
            await session.scalar(select(func.count()).select_from(Chunk)) or 0
        )
        checksum_source = "|".join(
            f"{sample.chunk_id}:{sample.doc_id}" for sample in samples
        )
        await session.execute(update(EmbeddingIngest).values(is_active=False))
        session.add(
            EmbeddingIngest(
                provider="hashing",
                model_name=embedding.model_identity,
                dimension=settings.embedding_dimension,
                dataset_checksum=hashlib.sha256(
                    checksum_source.encode("utf-8")
                ).hexdigest(),
                document_count=document_count,
                chunk_count=chunk_count,
                ingest_version=f"{settings.embedding_ingest_version}-legacy-verified",
                is_active=True,
            )
        )
        await session.commit()
        print(
            "LEGACY_EMBEDDING_METADATA_OK "
            f"provider=hashing model={embedding.model_identity} "
            f"documents={document_count} chunks={chunk_count}"
        )
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
