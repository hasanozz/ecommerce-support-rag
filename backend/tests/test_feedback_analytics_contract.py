from __future__ import annotations

from backend.app.main import app
from backend.app.schemas.feedback import FeedbackAnalyticsResponse


def test_feedback_analytics_route_is_registered_without_admin_dependency():
    route = next(
        item
        for item in app.routes
        if getattr(item, "path", None) == "/api/admin/feedback-analytics"
    )

    dependency_names = {
        dependency.call.__name__
        for dependency in getattr(route, "dependant").dependencies
    }

    assert "require_admin" not in dependency_names


def test_feedback_analytics_empty_response_contract():
    payload = FeedbackAnalyticsResponse(
        total_feedback=0,
        helpful_count=0,
        unhelpful_count=0,
        helpful_rate=0,
        unhelpful_rate=0,
        average_confidence_score=None,
        category_breakdown=[],
        recent_feedback=[],
    )

    assert payload.model_dump(mode="json") == {
        "total_feedback": 0,
        "helpful_count": 0,
        "unhelpful_count": 0,
        "helpful_rate": 0.0,
        "unhelpful_rate": 0.0,
        "average_confidence_score": None,
        "category_breakdown": [],
        "recent_feedback": [],
    }
