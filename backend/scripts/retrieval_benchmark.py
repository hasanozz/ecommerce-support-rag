from __future__ import annotations

import asyncio
import json
from pathlib import Path
from statistics import mean
from typing import Any

from backend.app.database import SessionLocal, close_database
from backend.app.services.retrieval import RetrievalService


DEFAULT_FIXTURE = Path("backend/tests/fixtures/retrieval_benchmark.json")


def reciprocal_rank(ranked_ids: list[str], expected_doc_id: str) -> float:
    try:
        return 1.0 / (ranked_ids.index(expected_doc_id) + 1)
    except ValueError:
        return 0.0


async def evaluate_case(
    service: RetrievalService, case: dict[str, Any]
) -> dict[str, Any]:
    async with SessionLocal() as session:
        results = await service.grouped_search(
            session,
            case["query"],
            candidate_limit=30,
            max_documents=3,
            max_sections=6,
        )
    ranked_ids = [item.doc_id for item in results]
    expected_doc_id = case["expected_doc_id"]
    return {
        "query": case["query"],
        "expected_doc_id": expected_doc_id,
        "ranked_doc_ids": ranked_ids,
        "top_1": bool(ranked_ids and ranked_ids[0] == expected_doc_id),
        "top_3": expected_doc_id in ranked_ids[:3],
        "mrr": reciprocal_rank(ranked_ids, expected_doc_id),
        "best_score": results[0].best_score if results else 0.0,
    }


async def main() -> None:
    cases = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    service = RetrievalService()
    results = [await evaluate_case(service, case) for case in cases]
    summary = {
        "case_count": len(results),
        "top_1": round(mean(item["top_1"] for item in results), 4),
        "top_3": round(mean(item["top_3"] for item in results), 4),
        "mrr": round(mean(item["mrr"] for item in results), 4),
        "failures": [
            item for item in results if not item["top_3"]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
