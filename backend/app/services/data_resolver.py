from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DemoCart, DemoCoupon, DemoOrder, DemoPaymentAttempt, DemoProduct

from ..schemas.data_resolver import (
    DataResolutionStatus,
    DataResolverInput,
    DataResolverOutput,
    EntityReference,
    EntityResolutionResult,
    EntityType,
    EvidenceProvenance,
    EvidenceReference,
    MatchCandidate,
    MatchType,
    ReferenceType,
    ResolutionNextStep,
    ResolvedDataEntities,
)


USED_CONVERSATION_STATE = "USED_CONVERSATION_STATE"
USED_FRONTEND_CONTEXT = "USED_FRONTEND_CONTEXT"


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True, slots=True)
class ResolverRecord:
    entity_type: EntityType
    record_id: int
    display_label: str
    lookup_value: str
    owner_user_id: int | None = None


@dataclass(frozen=True, slots=True)
class ResolverMatch:
    record: ResolverRecord
    confidence: float
    match_type: MatchType


class DataResolverAdapter(Protocol):
    async def get_by_id(
        self, entity_type: EntityType, record_id: int, user_id: int
    ) -> ResolverRecord | None: ...

    async def find_exact(
        self, entity_type: EntityType, value: str, user_id: int
    ) -> list[ResolverRecord]: ...

    async def find_product_candidates(
        self, name: str, user_id: int
    ) -> list[ResolverMatch]: ...


class InMemoryDataResolverAdapter:
    """Read-only adapter for contract tests and local integration scaffolding."""

    def __init__(self, records: list[ResolverRecord] | None = None) -> None:
        self._records = tuple(records or [])

    def _visible_records(
        self, entity_type: EntityType, user_id: int
    ) -> list[ResolverRecord]:
        return [
            record
            for record in self._records
            if record.entity_type == entity_type
            and (record.owner_user_id is None or record.owner_user_id == user_id)
        ]

    async def get_by_id(
        self, entity_type: EntityType, record_id: int, user_id: int
    ) -> ResolverRecord | None:
        return next(
            (
                record
                for record in self._visible_records(entity_type, user_id)
                if record.record_id == record_id
            ),
            None,
        )

    async def find_exact(
        self, entity_type: EntityType, value: str, user_id: int
    ) -> list[ResolverRecord]:
        normalized = _normalize(value)
        return [
            record
            for record in self._visible_records(entity_type, user_id)
            if _normalize(record.lookup_value) == normalized
        ]

    async def find_product_candidates(
        self, name: str, user_id: int
    ) -> list[ResolverMatch]:
        normalized = _normalize(name)
        matches = [
            ResolverMatch(
                record=record,
                confidence=SequenceMatcher(
                    None, normalized, _normalize(record.lookup_value)
                ).ratio(),
                match_type=MatchType.FUZZY_NAME,
            )
            for record in self._visible_records(EntityType.PRODUCT, user_id)
        ]
        return sorted(matches, key=lambda item: (-item.confidence, item.record.record_id))


class SqlAlchemyDataResolverAdapter:
    """Minimal read-only adapter over the existing demo commerce models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, entity_type: EntityType, record_id: int, user_id: int
    ) -> ResolverRecord | None:
        model = self._model(entity_type)
        statement = select(model).where(model.id == record_id)
        if entity_type == EntityType.PRODUCT:
            statement = statement.where(DemoProduct.is_active.is_(True))
        elif entity_type in {EntityType.ORDER, EntityType.CART, EntityType.PAYMENT}:
            statement = statement.where(model.user_id == user_id)
        row = await self.session.scalar(statement)
        return self._record(entity_type, row) if row is not None else None

    async def find_exact(
        self, entity_type: EntityType, value: str, user_id: int
    ) -> list[ResolverRecord]:
        normalized = _normalize(value)
        if entity_type == EntityType.PRODUCT:
            rows = (
                await self.session.scalars(
                    select(DemoProduct).where(DemoProduct.is_active.is_(True)).limit(200)
                )
            ).all()
            exact_rows = [
                row
                for row in rows
                if self._product_exact_match(row, normalized)
            ]
            return [self._record(entity_type, row) for row in exact_rows]
        if entity_type == EntityType.ORDER:
            rows = (
                await self.session.scalars(
                    select(DemoOrder).where(
                        DemoOrder.user_id == user_id,
                        DemoOrder.order_no == value.strip().upper(),
                    )
                )
            ).all()
            return [self._record(entity_type, row) for row in rows]
        if entity_type == EntityType.COUPON:
            rows = (
                await self.session.scalars(
                    select(DemoCoupon).where(
                        DemoCoupon.code == value.strip().upper()
                    )
                )
            ).all()
            return [self._record(entity_type, row) for row in rows]
        return []

    async def find_product_candidates(
        self, name: str, user_id: int
    ) -> list[ResolverMatch]:
        del user_id
        normalized = _normalize(name)
        rows = (
            await self.session.scalars(
                select(DemoProduct).where(DemoProduct.is_active.is_(True)).limit(200)
            )
        ).all()
        matches = [
            ResolverMatch(
                record=self._record(EntityType.PRODUCT, row),
                confidence=self._product_candidate_score(normalized, row),
                match_type=MatchType.FUZZY_NAME,
            )
            for row in rows
        ]
        return sorted(matches, key=lambda item: (-item.confidence, item.record.record_id))

    @staticmethod
    def _model(entity_type: EntityType):
        return {
            EntityType.PRODUCT: DemoProduct,
            EntityType.ORDER: DemoOrder,
            EntityType.COUPON: DemoCoupon,
            EntityType.CART: DemoCart,
            EntityType.PAYMENT: DemoPaymentAttempt,
        }[entity_type]

    @staticmethod
    def _record(entity_type: EntityType, row: object) -> ResolverRecord:
        if entity_type == EntityType.PRODUCT:
            display_value = getattr(row, "name")
        elif entity_type == EntityType.ORDER:
            display_value = getattr(row, "order_no")
        elif entity_type == EntityType.COUPON:
            display_value = getattr(row, "code")
        elif entity_type == EntityType.CART:
            display_value = f"Cart {getattr(row, 'id')}"
        else:
            display_value = getattr(row, "provider_reference")
        return ResolverRecord(
            entity_type=entity_type,
            record_id=getattr(row, "id"),
            display_label=str(display_value),
            lookup_value=str(display_value),
            owner_user_id=getattr(row, "user_id", None),
        )

    @staticmethod
    def _product_exact_match(row: object, normalized_value: str) -> bool:
        candidates = [
            getattr(row, "name", ""),
            getattr(row, "sku", ""),
            f"{getattr(row, 'brand', '')} {getattr(row, 'name', '')}".strip(),
            f"{getattr(row, 'name', '')} {getattr(row, 'brand', '')}".strip(),
            getattr(row, "search_text", ""),
            getattr(row, "description", ""),
            getattr(row, "ai_context", ""),
        ]
        tags = getattr(row, "tags", []) or []
        candidates.extend(str(tag) for tag in tags if str(tag).strip())
        return any(_normalize(candidate) == normalized_value for candidate in candidates if candidate)

    @staticmethod
    def _product_candidate_score(normalized_query: str, row: object) -> float:
        fields = [
            getattr(row, "name", ""),
            getattr(row, "sku", ""),
            getattr(row, "brand", ""),
            getattr(row, "category", ""),
            getattr(row, "subcategory", ""),
            getattr(row, "search_text", ""),
            getattr(row, "description", ""),
            getattr(row, "ai_context", ""),
        ]
        tags = getattr(row, "tags", []) or []
        tokens = {
            token
            for token in _normalize(normalized_query).split(" ")
            if token and len(token) > 1
        }
        best_ratio = 0.0
        field_texts = [_normalize(value) for value in fields if str(value).strip()]
        field_texts.extend(_normalize(str(tag)) for tag in tags if str(tag).strip())
        for text in field_texts:
            best_ratio = max(best_ratio, SequenceMatcher(None, normalized_query, text).ratio())
        query_tokens = set(normalized_query.split())
        if query_tokens:
            overlap_scores = []
            for text in field_texts:
                text_tokens = set(text.split())
                overlap = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
                overlap_scores.append(overlap)
            token_overlap = max(overlap_scores, default=0.0)
        else:
            token_overlap = 0.0
        exact_bonus = 0.0
        for candidate in field_texts:
            if candidate == normalized_query:
                exact_bonus = 1.0
                break
            if normalized_query in candidate or candidate in normalized_query:
                exact_bonus = max(exact_bonus, 0.92)
        if tokens:
            for token in tokens:
                if any(token in text for text in field_texts):
                    exact_bonus = max(exact_bonus, 0.85)
        score = max(best_ratio, token_overlap, exact_bonus)
        return round(min(1.0, score), 4)


class DataResolver:
    """Resolves entity references without mutation, retrieval, LLMs, or actions."""

    def __init__(
        self,
        adapter: DataResolverAdapter,
        *,
        fuzzy_auto_resolve_threshold: float = 0.9,
        fuzzy_candidate_threshold: float = 0.6,
        fuzzy_margin: float = 0.1,
    ) -> None:
        self.adapter = adapter
        self.fuzzy_auto_resolve_threshold = fuzzy_auto_resolve_threshold
        self.fuzzy_candidate_threshold = fuzzy_candidate_threshold
        self.fuzzy_margin = fuzzy_margin

    async def resolve(self, resolver_input: DataResolverInput | dict) -> DataResolverOutput:
        request = (
            resolver_input
            if isinstance(resolver_input, DataResolverInput)
            else DataResolverInput.model_validate(resolver_input)
        )
        if request.context_plan.next_step == "FALLBACK":
            return DataResolverOutput(
                status=DataResolutionStatus.SKIP,
                next_step=ResolutionNextStep.SKIP,
            )

        references, missing, warnings = self._references(request)
        results: list[EntityResolutionResult] = []
        grouped_references: dict[EntityType, list[EntityReference]] = {}
        for reference in references:
            group = grouped_references.setdefault(reference.entity_type, [])
            identity = (reference.type, _normalize(str(reference.value)))
            if all(
                (item.type, _normalize(str(item.value))) != identity for item in group
            ):
                group.append(reference)
        for entity_type, entity_references in grouped_references.items():
            if len(entity_references) > 1:
                results.append(
                    EntityResolutionResult(
                        entity_type=entity_type,
                        input_reference=entity_references[0],
                        status=DataResolutionStatus.AMBIGUOUS,
                    )
                )
                continue
            results.append(
                await self._resolve_reference(request.user_id, entity_references[0])
            )
        return self._build_output(results, missing, warnings)

    def _references(
        self, request: DataResolverInput
    ) -> tuple[list[EntityReference], list[EntityType], list[str]]:
        references = list(request.entity_references)
        missing: list[EntityType] = []
        warnings: list[str] = []
        plan_entities = request.context_plan.resolved_entities
        sources = set(request.context_plan.data_sources)

        existing_types = {reference.entity_type for reference in references}
        if EntityType.PRODUCT not in existing_types and (
            plan_entities.product_name
            or plan_entities.product_id
            or "product_db" in sources
            or "review_db" in sources
        ):
            product_id, reference_type = self._context_id(
                plan_entities.product_id,
                request.frontend_context.current_product_id,
                request.conversation_state.last_product_id,
            )
            if product_id is not None:
                references.append(
                    EntityReference(
                        entity_type=EntityType.PRODUCT,
                        type=reference_type,
                        value=product_id,
                    )
                )
                warnings.append(
                    USED_FRONTEND_CONTEXT
                    if reference_type == ReferenceType.FRONTEND_ID
                    else USED_CONVERSATION_STATE
                )
            elif plan_entities.product_name:
                references.append(
                    EntityReference(
                        entity_type=EntityType.PRODUCT,
                        type=ReferenceType.NAME,
                        value=plan_entities.product_name,
                    )
                )
            
        if EntityType.ORDER not in existing_types and (
            plan_entities.order_no or plan_entities.order_id
        ):
            if plan_entities.order_no:
                references.append(
                    EntityReference(
                        entity_type=EntityType.ORDER,
                        type=ReferenceType.ORDER_NO,
                        value=plan_entities.order_no,
                    )
                )
            else:
                order_id, reference_type = self._context_id(
                    plan_entities.order_id,
                    request.frontend_context.current_order_id,
                    request.conversation_state.last_order_id,
                )
                if order_id is None:
                    missing.append(EntityType.ORDER)
                else:
                    references.append(
                        EntityReference(
                            entity_type=EntityType.ORDER,
                            type=reference_type,
                            value=order_id,
                        )
                    )
                    warnings.append(
                        USED_FRONTEND_CONTEXT
                        if reference_type == ReferenceType.FRONTEND_ID
                        else USED_CONVERSATION_STATE
                    )

        if EntityType.COUPON not in existing_types and (
            plan_entities.coupon_code or "coupon_db" in sources
        ):
            if plan_entities.coupon_code:
                references.append(
                    EntityReference(
                        entity_type=EntityType.COUPON,
                        type=ReferenceType.COUPON_CODE,
                        value=plan_entities.coupon_code,
                    )
                )
            else:
                missing.append(EntityType.COUPON)

        return references, list(dict.fromkeys(missing)), list(dict.fromkeys(warnings))

    @staticmethod
    def _context_id(
        planned_id: int | None,
        frontend_id: int | None,
        state_id: int | None,
    ) -> tuple[int | None, ReferenceType]:
        if planned_id is not None:
            if planned_id == frontend_id:
                return planned_id, ReferenceType.FRONTEND_ID
            if planned_id == state_id:
                return planned_id, ReferenceType.STATE_ID
            return planned_id, ReferenceType.ID
        if frontend_id is not None:
            return frontend_id, ReferenceType.FRONTEND_ID
        return state_id, ReferenceType.STATE_ID

    async def _resolve_reference(
        self, user_id: int, reference: EntityReference
    ) -> EntityResolutionResult:
        if reference.type in {
            ReferenceType.ID,
            ReferenceType.STATE_ID,
            ReferenceType.FRONTEND_ID,
        }:
            record = await self.adapter.get_by_id(
                reference.entity_type, int(reference.value), user_id
            )
            match_type = {
                ReferenceType.STATE_ID: MatchType.CONVERSATION_STATE,
                ReferenceType.FRONTEND_ID: MatchType.FRONTEND_CONTEXT,
            }.get(reference.type, MatchType.EXACT_ID)
            return self._single_record_result(reference, record, match_type)
        if reference.entity_type == EntityType.PRODUCT and reference.type == ReferenceType.NAME:
            return await self._resolve_product_name(user_id, reference)
        match_type = {
            ReferenceType.ORDER_NO: MatchType.EXACT_ORDER_NO,
            ReferenceType.COUPON_CODE: MatchType.EXACT_COUPON_CODE,
        }.get(reference.type)
        if match_type is None:
            return self._unresolved(reference, DataResolutionStatus.NEEDS_CLARIFICATION)
        records = await self.adapter.find_exact(
            reference.entity_type, str(reference.value), user_id
        )
        if not records:
            return self._unresolved(reference, DataResolutionStatus.NO_MATCH)
        if len(records) > 1:
            return self._ambiguous(reference, records, match_type)
        return self._single_record_result(reference, records[0], match_type)

    async def _resolve_product_name(
        self, user_id: int, reference: EntityReference
    ) -> EntityResolutionResult:
        exact = await self.adapter.find_exact(
            EntityType.PRODUCT, str(reference.value), user_id
        )
        if len(exact) == 1:
            return self._single_record_result(reference, exact[0], MatchType.EXACT_NAME)
        if len(exact) > 1:
            return self._single_record_result(
                reference,
                exact[0],
                MatchType.EXACT_NAME,
                confidence=0.95,
            )

        candidates = [
            match
            for match in await self.adapter.find_product_candidates(
                str(reference.value), user_id
            )
            if match.confidence >= self.fuzzy_candidate_threshold
        ]
        if not candidates:
            return self._unresolved(reference, DataResolutionStatus.NO_MATCH)
        top = candidates[0]
        runner_up = candidates[1].confidence if len(candidates) > 1 else 0.0
        if (
            top.confidence >= self.fuzzy_auto_resolve_threshold
            and top.confidence - runner_up >= self.fuzzy_margin
        ):
            return self._single_record_result(
                reference,
                top.record,
                MatchType.FUZZY_NAME,
                confidence=top.confidence,
            )
        return self._single_record_result(
            reference,
            top.record,
            MatchType.FUZZY_NAME,
            confidence=top.confidence,
        )

    def _single_record_result(
        self,
        reference: EntityReference,
        record: ResolverRecord | None,
        match_type: MatchType,
        *,
        confidence: float = 1.0,
    ) -> EntityResolutionResult:
        if record is None:
            return self._unresolved(reference, DataResolutionStatus.NO_MATCH)
        source = self._source(reference.entity_type)
        return EntityResolutionResult(
            entity_type=reference.entity_type,
            input_reference=reference,
            status=DataResolutionStatus.RESOLVED,
            resolved_id=record.record_id,
            match_type=match_type,
            confidence=confidence,
            provenance=EvidenceProvenance(source=source, record_id=record.record_id),
        )

    def _ambiguous(
        self,
        reference: EntityReference,
        records: list[ResolverRecord],
        match_type: MatchType,
    ) -> EntityResolutionResult:
        return EntityResolutionResult(
            entity_type=reference.entity_type,
            input_reference=reference,
            status=DataResolutionStatus.AMBIGUOUS,
            candidates=[
                MatchCandidate(
                    record_id=record.record_id,
                    display_label=record.display_label,
                    confidence=1.0,
                    match_type=match_type,
                )
                for record in records[:5]
            ],
        )

    @staticmethod
    def _unresolved(
        reference: EntityReference, status: DataResolutionStatus
    ) -> EntityResolutionResult:
        return EntityResolutionResult(
            entity_type=reference.entity_type,
            input_reference=reference,
            status=status,
        )

    @staticmethod
    def _match_candidate(match: ResolverMatch) -> MatchCandidate:
        return MatchCandidate(
            record_id=match.record.record_id,
            display_label=match.record.display_label,
            confidence=match.confidence,
            match_type=match.match_type,
        )

    def _build_output(
        self,
        results: list[EntityResolutionResult],
        missing: list[EntityType],
        warnings: list[str],
    ) -> DataResolverOutput:
        ambiguous = [
            result.entity_type
            for result in results
            if result.status == DataResolutionStatus.AMBIGUOUS
        ]
        no_matches = [
            result.entity_type
            for result in results
            if result.status == DataResolutionStatus.NO_MATCH
        ]
        clarifications = [
            result.entity_type
            for result in results
            if result.status == DataResolutionStatus.NEEDS_CLARIFICATION
        ]
        resolved = [
            result
            for result in results
            if result.status == DataResolutionStatus.RESOLVED
            and result.resolved_id is not None
        ]
        if ambiguous:
            status = DataResolutionStatus.AMBIGUOUS
        elif no_matches and resolved:
            status = DataResolutionStatus.PARTIALLY_RESOLVED
        elif no_matches:
            status = DataResolutionStatus.NO_MATCH
        elif clarifications:
            status = (
                DataResolutionStatus.PARTIALLY_RESOLVED
                if resolved
                else DataResolutionStatus.NEEDS_CLARIFICATION
            )
        elif missing:
            status = (
                DataResolutionStatus.PARTIALLY_RESOLVED
                if resolved
                else DataResolutionStatus.NEEDS_CLARIFICATION
            )
        elif resolved:
            status = DataResolutionStatus.RESOLVED
        else:
            status = DataResolutionStatus.SKIP

        resolved_entities = ResolvedDataEntities()
        evidence_refs: list[EvidenceReference] = []
        for result in resolved:
            setattr(
                resolved_entities,
                f"{result.entity_type.value.casefold()}_id",
                result.resolved_id,
            )
            if result.provenance:
                evidence_refs.append(
                    EvidenceReference(
                        entity_type=result.entity_type,
                        source=result.provenance.source,
                        record_id=result.provenance.record_id,
                    )
                )
        next_step = (
            ResolutionNextStep.FETCH_EVIDENCE
            if status == DataResolutionStatus.RESOLVED
            else ResolutionNextStep.SKIP
            if status == DataResolutionStatus.SKIP
            else ResolutionNextStep.ASK_CLARIFICATION
        )
        return DataResolverOutput(
            status=status,
            resolved_entities=resolved_entities,
            entity_results=results,
            missing_entities=list(
                dict.fromkeys(missing + no_matches + clarifications)
            ),
            ambiguous_entities=list(dict.fromkeys(ambiguous)),
            evidence_refs=evidence_refs,
            warnings=warnings,
            next_step=next_step,
        )

    @staticmethod
    def _source(entity_type: EntityType) -> str:
        return {
            EntityType.PRODUCT: "PRODUCT_CATALOG",
            EntityType.ORDER: "ORDER_LEDGER",
            EntityType.COUPON: "COUPON_CATALOG",
            EntityType.CART: "CART",
            EntityType.PAYMENT: "PAYMENT_LEDGER",
        }[entity_type]
