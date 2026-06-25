from __future__ import annotations

import asyncio
import hashlib

from sqlalchemy import delete, update

from backend.app.config import get_settings
from backend.app.database import SessionLocal, close_database, initialize_database
from backend.app.models import Chunk, Document, EmbeddingIngest
from backend.app.rag.chunking import load_final_rag_sources
from backend.app.services.embedding import get_embedding_service
from backend.app.services.embedding_compatibility import (
    validate_database_dimensions,
    validate_model_dimension,
)


async def main() -> None:
    settings = get_settings()
    documents_path = settings.rag_documents_final_path
    chunks_path = settings.rag_chunks_clean_path
    documents, chunks = load_final_rag_sources(documents_path, chunks_path)

    embedding_service = get_embedding_service()
    actual_dimension = validate_model_dimension(settings, embedding_service)
    vectors: list[list[float]] = []
    batch_size = 32
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors.extend(
            embedding_service.embed_documents(
                [item["contextual_content"] for item in batch]
            )
        )
    if any(len(vector) != actual_dimension for vector in vectors):
        raise RuntimeError("Üretilen embedding vektörlerinin boyutları tutarsız.")

    await initialize_database()
    async with SessionLocal() as session:
        await validate_database_dimensions(session, actual_dimension)
        checksum = hashlib.sha256()
        for document_file in sorted(documents_path.glob("*.json")):
            checksum.update(document_file.read_bytes())
        dataset_checksum = checksum.hexdigest()
        await session.execute(delete(Chunk))
        await session.execute(delete(Document))
        session.add_all(
            [
                Document(
                    id=item["id"],
                    category=item["category"],
                    subcategory=item["subcategory"],
                    title=item["title"],
                    raw_json=item,
                )
                for item in documents
            ]
        )
        await session.flush()
        session.add_all(
            [
                Chunk(**chunk, embedding=embedding)
                for chunk, embedding in zip(chunks, vectors, strict=True)
            ]
        )
        await session.execute(
            update(EmbeddingIngest).values(is_active=False)
        )
        session.add(
            EmbeddingIngest(
                provider=settings.embedding_provider,
                model_name=embedding_service.model_identity,
                dimension=actual_dimension,
                dataset_checksum=dataset_checksum,
                document_count=len(documents),
                chunk_count=len(chunks),
                ingest_version=settings.embedding_ingest_version,
                is_active=True,
            )
        )
        await session.commit()
    await close_database()
    print(f"INGEST_OK documents={len(documents)} chunks={len(chunks)}")


if __name__ == "__main__":
    asyncio.run(main())
