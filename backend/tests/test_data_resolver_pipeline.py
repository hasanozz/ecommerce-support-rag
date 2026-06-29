from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.models import Message, RagRun
from backend.app.schemas.context_resolver import (
    ContextResolverOutput,
    ResolvedEntities,
)
from backend.app.schemas.data_resolver import (
    DataResolutionStatus,
    DataResolverOutput,
    EntityReference,
    EntityResolutionResult,
    EntityType,
    ReferenceType,
    ResolutionNextStep,
    ResolvedDataEntities,
)
from backend.app.schemas.evidence_fetcher import (
    EvidenceEntityType,
    EvidenceFetcherOutput,
    EvidenceItem,
    EvidenceProvenance,
    EvidencePurpose,
)
from backend.app.services.classifier import ClassificationResult
from backend.app.services.pipeline import SupportPipeline
from backend.app.services.evidence_fetcher import SqlAlchemyEvidenceFetcherAdapter


class ResultRows:
    def all(self):
        return []


class FakeSession:
    def __init__(self):
        self._next_message_id = 1
        self.added = []

    async def execute(self, statement):
        del statement
        return ResultRows()

    async def scalar(self, statement):
        del statement
        return None

    def add(self, item):
        self.added.append(item)
        if isinstance(item, Message) and item.id is None:
            item.id = self._next_message_id
            self._next_message_id += 1

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, item):
        del item


def test_default_pipeline_has_read_only_sql_evidence_fetcher():
    pipeline = SupportPipeline()

    assert pipeline.evidence_fetcher is not None
    assert isinstance(
        pipeline.evidence_fetcher.adapter, SqlAlchemyEvidenceFetcherAdapter
    )
    assert pipeline.evidence_fetcher.adapter.session is None


def context_plan(
    *,
    needs_support_rag=False,
    entities=None,
    sources=None,
    next_step="FETCH_CONTEXT",
    needs_clarification=False,
):
    return ContextResolverOutput(
        resolved_entities=ResolvedEntities(**(entities or {})),
        data_sources=sources or ["product_db"],
        fields=["stock"],
        needs_support_rag=needs_support_rag,
        needs_clarification=needs_clarification,
        clarification_reason=(
            "PRODUCT_CONTEXT_REQUIRED" if needs_clarification else None
        ),
        next_step=next_step,
        confidence=0.9,
    )


def entity_result(entity_type, status, *, resolved_id=None, reference=None):
    reference = reference or EntityReference(
        entity_type=entity_type,
        type=ReferenceType.NAME if entity_type == EntityType.PRODUCT else ReferenceType.ID,
        value="reference" if entity_type == EntityType.PRODUCT else 1,
    )
    return EntityResolutionResult(
        entity_type=entity_type,
        input_reference=reference,
        status=status,
        resolved_id=resolved_id,
        confidence=1.0 if resolved_id else 0.0,
    )


def data_result(status, *, result=None, resolved=None, missing=None, ambiguous=None):
    next_step = (
        ResolutionNextStep.FETCH_EVIDENCE
        if status == DataResolutionStatus.RESOLVED
        else ResolutionNextStep.SKIP
        if status == DataResolutionStatus.SKIP
        else ResolutionNextStep.ASK_CLARIFICATION
    )
    return DataResolverOutput(
        status=status,
        resolved_entities=ResolvedDataEntities(**(resolved or {})),
        entity_results=[result] if result else [],
        missing_entities=missing or [],
        ambiguous_entities=ambiguous or [],
        next_step=next_step,
    )


def configured_pipeline(plan, resolution, *, product_route="product_only"):
    pipeline = SupportPipeline()
    classification = ClassificationResult(
        category="SIPARIS",
        subcategory="",
        priority="MEDIUM",
        expected_action="RAG_ANSWER",
        confidence=0.9,
        intent="PRODUCT_STOCK",
    )
    pipeline.classifier = SimpleNamespace(
        classify=AsyncMock(return_value=classification),
        last_usage={},
    )
    pipeline.rewriter = SimpleNamespace(
        rewrite=AsyncMock(
            return_value={
                "canonical_query": "stokta mı?",
                "category": "SIPARIS",
                "is_in_scope": True,
            }
        )
    )
    pipeline.context_resolver = SimpleNamespace(resolve=Mock(return_value=plan))
    pipeline.data_resolver = SimpleNamespace(resolve=AsyncMock(return_value=resolution))
    pipeline.product_context = SimpleNamespace(
        _load_state=AsyncMock(return_value=None),
        build=AsyncMock(
            return_value={
                "route_mode": product_route,
                "category": "SIPARIS",
                "context_type": "intent",
                "items": ["product evidence"],
                "text": "product evidence",
                "decision_hints": [],
                "primary_product": {"id": 15, "name": "Çay Bardağı"},
                "selected_product_ids": [15],
            }
        ),
        update_state=AsyncMock(),
    )
    pipeline.customer_context = SimpleNamespace(
        build=AsyncMock(
            return_value={
                "category": "SIPARIS",
                "intent": "",
                "context_type": "intent",
                "items": [],
                "text": "support evidence",
                "decision_hints": [],
            }
        )
    )
    pipeline.retrieval = SimpleNamespace(
        grouped_search=AsyncMock(return_value=[]),
        grouped_by_category=AsyncMock(return_value=[]),
    )
    pipeline.reranker = SimpleNamespace(
        rerank=AsyncMock(side_effect=lambda query, grouped: (grouped, None))
    )
    pipeline.similar = SimpleNamespace(
        search=AsyncMock(return_value=[]),
        record_impressions=AsyncMock(),
    )
    pipeline.context_builder = SimpleNamespace(build=Mock(return_value=""))
    pipeline.gemini = SimpleNamespace(
        enabled=True,
        last_usage={},
        model_name=Mock(return_value="gemini-test"),
        answer=AsyncMock(return_value={"answer": "resolved answer", "cited_doc_ids": []}),
    )
    return pipeline


async def run_pipeline(pipeline):
    result, _ = await run_pipeline_with_session(pipeline)
    return result


async def run_pipeline_with_session(pipeline):
    session = FakeSession()
    result = await pipeline.run(
        session,
        SimpleNamespace(id=10, user_id=1, title="Test"),
        SimpleNamespace(id=1),
        "stokta mı?",
        "ip-hash",
        frontend_context={},
    )
    return result, session


@pytest.mark.asyncio
async def test_resolved_data_allows_pipeline_to_continue():
    plan = context_plan()
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.RESOLVED, resolved_id=15),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(plan, resolution)

    await run_pipeline(pipeline)

    pipeline.data_resolver.resolve.assert_awaited_once()
    pipeline.product_context.build.assert_awaited_once()
    assert pipeline.product_context.build.await_args.kwargs["frontend_context"][
        "current_product_id"
    ] == 15


@pytest.mark.asyncio
async def test_no_match_returns_product_clarification_without_gemini_or_context():
    plan = context_plan(entities={"product_name": "missing product"})
    resolution = data_result(
        DataResolutionStatus.NO_MATCH,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.NO_MATCH),
        missing=[EntityType.PRODUCT],
    )
    pipeline = configured_pipeline(plan, resolution)

    assistant, *_ = await run_pipeline(pipeline)

    assert "ürünü bulamadım" in assistant.safe_content
    pipeline.product_context.build.assert_not_awaited()
    pipeline.customer_context.build.assert_not_awaited()
    pipeline.retrieval.grouped_search.assert_not_awaited()
    pipeline.gemini.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_returns_clarification_without_gemini():
    resolution = data_result(
        DataResolutionStatus.AMBIGUOUS,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.AMBIGUOUS),
        ambiguous=[EntityType.PRODUCT],
    )
    pipeline = configured_pipeline(context_plan(), resolution)

    assistant, *_ = await run_pipeline(pipeline)

    assert "Birden fazla olası kayıt" in assistant.safe_content
    pipeline.product_context.build.assert_not_awaited()
    pipeline.gemini.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_needs_clarification_returns_order_specific_message():
    resolution = data_result(
        DataResolutionStatus.NEEDS_CLARIFICATION,
        result=entity_result(EntityType.ORDER, DataResolutionStatus.NEEDS_CLARIFICATION),
        missing=[EntityType.ORDER],
    )
    pipeline = configured_pipeline(context_plan(sources=["order_db"]), resolution)

    assistant, *_ = await run_pipeline(pipeline)

    assert "siparişi bulamadım" in assistant.safe_content
    pipeline.customer_context.build.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_safely_continues_existing_context_flow():
    pipeline = configured_pipeline(
        context_plan(), data_result(DataResolutionStatus.SKIP)
    )

    await run_pipeline(pipeline)

    pipeline.product_context.build.assert_awaited_once()
    pipeline.gemini.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_clarification_does_not_call_data_resolver():
    plan = context_plan(next_step="CLARIFY", needs_clarification=True)
    pipeline = configured_pipeline(plan, data_result(DataResolutionStatus.SKIP))

    await run_pipeline(pipeline)

    pipeline.data_resolver.resolve.assert_not_awaited()
    pipeline.product_context.build.assert_not_awaited()


def test_partially_resolved_without_required_gaps_can_continue():
    result = data_result(DataResolutionStatus.PARTIALLY_RESOLVED)

    assert SupportPipeline._data_resolution_allows_context(result) is True


def test_partially_resolved_with_missing_entity_is_blocked():
    result = data_result(
        DataResolutionStatus.PARTIALLY_RESOLVED,
        missing=[EntityType.ORDER],
    )

    assert SupportPipeline._data_resolution_allows_context(result) is False


@pytest.mark.asyncio
async def test_order_no_match_does_not_call_customer_context():
    reference = EntityReference(
        entity_type=EntityType.ORDER,
        type=ReferenceType.ORDER_NO,
        value="DMO-MISSING",
    )
    resolution = data_result(
        DataResolutionStatus.NO_MATCH,
        result=entity_result(
            EntityType.ORDER, DataResolutionStatus.NO_MATCH, reference=reference
        ),
        missing=[EntityType.ORDER],
    )
    pipeline = configured_pipeline(context_plan(sources=["order_db"]), resolution)

    await run_pipeline(pipeline)

    pipeline.customer_context.build.assert_not_awaited()
    pipeline.product_context.build.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_without_support_rag_skips_retrieval():
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.RESOLVED, resolved_id=15),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(context_plan(needs_support_rag=False), resolution)

    await run_pipeline(pipeline)

    pipeline.retrieval.grouped_search.assert_not_awaited()
    pipeline.retrieval.grouped_by_category.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_with_support_rag_keeps_retrieval_flow():
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.RESOLVED, resolved_id=15),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(
        context_plan(needs_support_rag=True),
        resolution,
        product_route="product_support_mixed",
    )

    await run_pipeline(pipeline)

    pipeline.retrieval.grouped_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_data_resolution_is_written_to_assistant_metadata():
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.RESOLVED, resolved_id=15),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(context_plan(), resolution)

    (assistant, *_), session = await run_pipeline_with_session(pipeline)

    metadata = assistant.security_metadata["debug"]["data_resolver"]
    assert metadata["status"] == "RESOLVED"
    assert metadata["resolved_entities"]["product_id"] == 15
    rag_run = next(item for item in session.added if isinstance(item, RagRun))
    assert rag_run.classification_result["data_resolver"]["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_explicit_entity_and_old_state_are_passed_without_state_override():
    plan = context_plan(entities={"product_name": "new product"})
    resolution = data_result(
        DataResolutionStatus.NO_MATCH,
        result=entity_result(EntityType.PRODUCT, DataResolutionStatus.NO_MATCH),
        missing=[EntityType.PRODUCT],
    )
    pipeline = configured_pipeline(plan, resolution)
    pipeline.product_context._load_state.return_value = SimpleNamespace(
        last_product_id=99,
        last_order_id=None,
        last_cart_id=None,
        last_payment_id=None,
        last_intent="PRODUCT_ATTRIBUTE",
        last_action="show_product",
    )

    await run_pipeline(pipeline)

    resolver_payload = pipeline.data_resolver.resolve.await_args.args[0]
    assert resolver_payload["context_plan"]["resolved_entities"]["product_name"] == "new product"
    assert resolver_payload["conversation_state"]["last_product_id"] == 99
    pipeline.product_context.build.assert_not_awaited()


@pytest.mark.asyncio
async def test_evidence_fetcher_error_is_non_fatal_and_recorded_safely():
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(
            EntityType.PRODUCT,
            DataResolutionStatus.RESOLVED,
            resolved_id=15,
        ),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(context_plan(), resolution)
    pipeline.evidence_fetcher = SimpleNamespace(
        fetch=AsyncMock(
            side_effect=RuntimeError("database password must not be exposed")
        )
    )

    assistant, *_ = await run_pipeline(pipeline)

    assert assistant.safe_content == "resolved answer"
    pipeline.gemini.answer.assert_awaited_once()
    warnings = assistant.security_metadata["debug"]["warnings"]
    assert "EVIDENCE_FETCHER_ERROR:RuntimeError" in warnings
    assert "database password" not in str(assistant.security_metadata)


@pytest.mark.asyncio
async def test_pipeline_passes_structured_evidence_to_gemini():
    resolution = data_result(
        DataResolutionStatus.RESOLVED,
        result=entity_result(
            EntityType.PRODUCT,
            DataResolutionStatus.RESOLVED,
            resolved_id=15,
        ),
        resolved={"product_id": 15},
    )
    pipeline = configured_pipeline(context_plan(), resolution)
    evidence = EvidenceFetcherOutput(
        product_evidence=[
            EvidenceItem(
                source="PRODUCT_CATALOG",
                entity_type=EvidenceEntityType.PRODUCT,
                entity_id=15,
                purpose=EvidencePurpose.PRODUCT_STOCK,
                data={"stock": 3, "availability": "IN_STOCK"},
                provenance=EvidenceProvenance(
                    source="PRODUCT_CATALOG", record_id=15
                ),
            )
        ]
    )
    pipeline.evidence_fetcher = SimpleNamespace(
        fetch=AsyncMock(return_value=evidence)
    )

    await run_pipeline(pipeline)

    kwargs = pipeline.gemini.answer.await_args.kwargs
    assert kwargs["original_user_message"] == "stokta mı?"
    assert kwargs["resolved_entities"]["product_id"] == 15
    assert kwargs["evidence_pack"]["product_evidence"][0]["data"]["stock"] == 3
    assert kwargs["answer_scope"]["evidence_only"] is True
    assert kwargs["answer_scope"]["actions_performed"] is False
