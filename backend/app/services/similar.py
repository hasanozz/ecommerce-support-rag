from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..models import SimilarSolution, SimilarSolutionImpression
from .embedding import EmbeddingService, get_embedding_service


class SimilarSolutionService:
    def __init__(
        self,
        embedding: EmbeddingService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding = embedding or get_embedding_service()

    async def search(
        self,
        session: AsyncSession,
        query: str,
        category: str | None,
        limit: int = 3,
    ) -> list[tuple[SimilarSolution, float, int]]:
        vector = self.embedding.embed_query(query)
        distance = SimilarSolution.embedding.cosine_distance(vector)
        impression_count = (
            select(func.count(SimilarSolutionImpression.id))
            .where(
                SimilarSolutionImpression.similar_solution_id == SimilarSolution.id
            )
            .correlate(SimilarSolution)
            .scalar_subquery()
        )
        statement = select(
            SimilarSolution,
            distance.label("distance"),
            impression_count.label("view_count"),
        ).where(
            or_(
                SimilarSolution.is_published.is_(True),
                (
                    (SimilarSolution.helpful_count >= self.settings.similar_solution_min_helpful)
                    & (
                        SimilarSolution.success_rate
                        >= self.settings.similar_solution_min_success_rate
                    )
                ),
            )
        )
        if category and category != "GENEL_DESTEK":
            statement = statement.where(SimilarSolution.category == category)
        rows = (await session.execute(statement.order_by(distance).limit(limit))).all()
        return [
            (
                solution,
                round(max(0.0, 1.0 - float(row_distance)), 4),
                int(view_count or 0),
            )
            for solution, row_distance, view_count in rows
        ]

    async def record_impressions(
        self,
        session: AsyncSession,
        matches: list[tuple[SimilarSolution, float, int]],
        assistant_message_id: int,
        user_id: int,
    ) -> None:
        for solution, _, _ in matches:
            statement = (
                insert(SimilarSolutionImpression)
                .values(
                    similar_solution_id=solution.id,
                    assistant_message_id=assistant_message_id,
                    user_id=user_id,
                )
                .on_conflict_do_nothing(
                    constraint="uq_similar_solution_impression"
                )
            )
            await session.execute(statement)

    async def upsert_from_answer(
        self,
        session: AsyncSession,
        canonical_question: str,
        safe_answer: str,
        category: str,
        helpful_count: int,
        unhelpful_count: int,
    ) -> SimilarSolution:
        existing = await session.scalar(
            select(SimilarSolution).where(
                SimilarSolution.canonical_question == canonical_question
            )
        )
        total = helpful_count + unhelpful_count
        success_rate = helpful_count / total if total else 0.0
        published = False
        if existing is None:
            existing = SimilarSolution(
                canonical_question=canonical_question,
                safe_answer=safe_answer,
                category=category,
                embedding=self.embedding.embed_query(canonical_question),
            )
            session.add(existing)
        existing.safe_answer = safe_answer
        existing.helpful_count = helpful_count
        existing.unhelpful_count = unhelpful_count
        existing.success_rate = success_rate
        existing.is_published = existing.is_published or published
        await session.flush()
        return existing

    async def refresh_publication(
        self, session: AsyncSession, solution: SimilarSolution
    ) -> int:
        view_count = int(
            await session.scalar(
                select(func.count(SimilarSolutionImpression.id)).where(
                    SimilarSolutionImpression.similar_solution_id == solution.id
                )
            )
            or 0
        )
        solution.is_published = (
            view_count >= self.settings.similar_solution_min_views
            and solution.helpful_count >= self.settings.similar_solution_min_helpful
            and solution.success_rate
            >= self.settings.similar_solution_min_success_rate
        )
        return view_count
