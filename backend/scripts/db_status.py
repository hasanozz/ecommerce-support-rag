from __future__ import annotations

import asyncio

from sqlalchemy import func, select, text

from backend.app.database import SessionLocal, close_database
from backend.app.models import Chunk, Document, QueryLog


async def main() -> None:
    async with SessionLocal() as session:
        vector_enabled = await session.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        document_count = await session.scalar(
            select(func.count()).select_from(Document)
        )
        chunk_count = await session.scalar(select(func.count()).select_from(Chunk))
        query_log_count = await session.scalar(
            select(func.count()).select_from(QueryLog)
        )

        print(f"pgvector: {'enabled' if vector_enabled else 'missing'}")
        print(f"documents: {document_count}")
        print(f"chunks: {chunk_count}")
        print(f"query_logs: {query_log_count}")

    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
