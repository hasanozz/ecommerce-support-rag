from __future__ import annotations

import asyncio
import json

from sqlalchemy import delete

from backend.app.config import get_settings
from backend.app.database import SessionLocal, close_database, initialize_database
from backend.app.models import Chunk, Document
from backend.app.rag.chunking import create_chunks, load_documents
from backend.app.services.embedding import get_embedding_service


async def main() -> None:
    settings = get_settings()
    documents_path = settings.processed_data_path / "rag_documents.jsonl"
    chunks_path = settings.processed_data_path / "rag_chunks.jsonl"
    documents = load_documents(documents_path)
    chunks = create_chunks(documents_path, chunks_path)

    embedding_service = get_embedding_service()
    vectors: list[list[float]] = []
    batch_size = 32
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors.extend(
            embedding_service.embed_documents(
                [item["contextual_content"] for item in batch]
            )
        )

    await initialize_database()
    async with SessionLocal() as session:
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
        await session.commit()
    await close_database()
    print(f"INGEST_OK documents={len(documents)} chunks={len(chunks)}")


if __name__ == "__main__":
    asyncio.run(main())
