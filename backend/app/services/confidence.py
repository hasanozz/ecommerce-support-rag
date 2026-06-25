from __future__ import annotations

from ..config import Settings


def composite_confidence(
    retrieval_score: float,
    reranker_score: float | None,
    classifier_confidence: float | None,
) -> float | None:
    if classifier_confidence is None:
        return None
    values = [retrieval_score, classifier_confidence]
    if reranker_score is not None:
        values.append(reranker_score)
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("Confidence bileşenleri 0 ile 1 arasında olmalıdır.")
    if reranker_score is None:
        return round(0.70 * retrieval_score + 0.30 * classifier_confidence, 4)
    return round(
        0.50 * retrieval_score
        + 0.30 * reranker_score
        + 0.20 * classifier_confidence,
        4,
    )


def confidence_label(score: float | None, settings: Settings) -> str | None:
    if score is None:
        return None
    if score >= settings.confidence_high_threshold:
        return "HIGH"
    if score >= settings.confidence_medium_threshold:
        return "MEDIUM"
    return "LOW"
