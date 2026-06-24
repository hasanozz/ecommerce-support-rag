from __future__ import annotations

import asyncio

from sqlalchemy import func, select, text

from backend.app.database import SessionLocal, close_database
from backend.app.models import (
    Chunk,
    Conversation,
    Document,
    EmbeddingIngest,
    Feedback,
    QueryLog,
    SimilarSolution,
    SimilarSolutionImpression,
    Ticket,
    User,
    DemoCart,
    DemoCoupon,
    DemoOrder,
    DemoPaymentAttempt,
    DemoProduct,
)


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
        user_count = await session.scalar(select(func.count()).select_from(User))
        conversation_count = await session.scalar(
            select(func.count()).select_from(Conversation)
        )
        feedback_count = await session.scalar(
            select(func.count()).select_from(Feedback)
        )
        ticket_count = await session.scalar(select(func.count()).select_from(Ticket))
        solution_count = await session.scalar(
            select(func.count()).select_from(SimilarSolution)
        )
        impression_count = await session.scalar(
            select(func.count()).select_from(SimilarSolutionImpression)
        )
        active_ingest_count = await session.scalar(
            select(func.count())
            .select_from(EmbeddingIngest)
            .where(EmbeddingIngest.is_active.is_(True))
        )
        product_count = await session.scalar(select(func.count()).select_from(DemoProduct))
        coupon_count = await session.scalar(select(func.count()).select_from(DemoCoupon))
        cart_count = await session.scalar(select(func.count()).select_from(DemoCart))
        order_count = await session.scalar(select(func.count()).select_from(DemoOrder))
        payment_attempt_count = await session.scalar(
            select(func.count()).select_from(DemoPaymentAttempt)
        )

        print(f"pgvector: {'enabled' if vector_enabled else 'missing'}")
        print(f"documents: {document_count}")
        print(f"chunks: {chunk_count}")
        print(f"query_logs: {query_log_count}")
        print(f"users: {user_count}")
        print(f"conversations: {conversation_count}")
        print(f"feedback: {feedback_count}")
        print(f"tickets: {ticket_count}")
        print(f"similar_solutions: {solution_count}")
        print(f"similar_solution_impressions: {impression_count}")
        print(f"active_embedding_ingests: {active_ingest_count}")
        print(f"demo_products: {product_count}")
        print(f"demo_coupons: {coupon_count}")
        print(f"demo_carts: {cart_count}")
        print(f"demo_orders: {order_count}")
        print(f"demo_payment_attempts: {payment_attempt_count}")

    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
