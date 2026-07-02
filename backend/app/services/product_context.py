from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Conversation,
    ConversationState,
    DemoCart,
    DemoCartItem,
    DemoCoupon,
    DemoOrder,
    DemoOrderItem,
    DemoPaymentAttempt,
    DemoProduct,
    DemoProductAlias,
    DemoProductFavorite,
    DemoProductReview,
    DemoRefund,
    DemoReturnRequest,
    DemoSavedCard,
    DemoShipment,
    DemoUserSecurityProfile,
    DemoWallet,
    User,
)
from .demo_commerce import money
from .embedding import get_embedding_service


PRODUCT_HINTS = {
    "fiyat",
    "stok",
    "iade",
    "garanti",
    "yorum",
    "puan",
    "ozellik",
    "özellik",
    "bilgi",
    "detay",
}

QUERY_STOPWORDS = {
    "hakkinda",
    "hakkında",
    "bilgi",
    "ver",
    "verir",
    "misin",
    "mısın",
    "mi",
    "mı",
    "mu",
    "mü",
    "bana",
    "anlat",
    "anlatsana",
    "ozellik",
    "özellik",
    "ozellikleri",
    "özellikleri",
    "detay",
    "detaylari",
    "detayları",
    "nedir",
    "ne",
    "kadar",
    "icin",
    "için",
}

SUPPORT_HINTS = {
    "sipariş",
    "kargo",
    "teslim",
    "iade",
    "refund",
    "kupon",
    "kampanya",
    "ödeme",
    "kart",
    "cüzdan",
    "wallet",
    "iptal",
    "fatura",
    "hesap",
    "güvenlik",
}

FOLLOWUP_HINTS = {
    "bu",
    "bunu",
    "bunun",
    "evet",
    "aç",
    "ac",
    "detay",
    "detayları",
    "detaylari",
    "ona",
    "onu",
    "onun",
    "o ürün",
    "o sipariş",
    "diğer sipariş",
    "peki",
    "tekrar",
    "yeniden",
    "favoriye ekle",
    "sepete ekle",
    "yorum",
    "puan",
    "değerlendirme",
    "degerlendirme",
    "stok",
    "iade",
    "garanti",
    "watt",
    "fiyat",
}

CORRECTION_HINTS = {
    "hayir",
    "hayır",
    "degil",
    "değil",
    "demedim",
    "sormadim",
    "sormadım",
    "kastettim",
    "kastetmedim",
    "baska",
    "başka",
    "yanlis",
    "yanlış",
}

ATTRIBUTE_LABELS = {
    "guc_watt": "motor gücü",
    "hazne_litre": "hazne kapasitesi",
    "hiz_kademesi": "hız kademesi",
    "pil_suresi_saat": "pil süresi",
    "laptop_bolmesi": "laptop bölmesi",
    "suya_dayanikli": "suya dayanıklı",
    "mikrofon": "mikrofon",
    "gramaj": "gramaj",
    "tip": "tip",
    "malzeme": "malzeme",
    "makinede_yikanabilir": "makinede yıkanabilir",
    "garanti": "garanti",
}

ATTRIBUTE_VALUE_LABELS = {
    "dokme": "dökme",
    "dökme": "dökme",
    "poset": "poşet",
    "poşet": "poşet",
}


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "").casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_any(text: str, terms: set[str] | tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


COMMON_TURKISH_SUFFIXES = (
    "nin",
    "nın",
    "nun",
    "nün",
    "in",
    "ın",
    "un",
    "ün",
    "im",
    "ım",
    "um",
    "üm",
    "si",
    "sı",
    "su",
    "sü",
    "yi",
    "yı",
    "yu",
    "yü",
    "de",
    "da",
    "den",
    "dan",
    "ten",
    "tan",
    "e",
    "a",
    "i",
    "ı",
    "u",
    "ü",
)


def _shrink_token(token: str) -> str:
    token = token.strip()
    for suffix in COMMON_TURKISH_SUFFIXES:
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _token_matches(term: str, token: str) -> bool:
    term = _shrink_token(term)
    token = _shrink_token(token)
    return term == token or term in token or token in term


def _display_attribute_key(key: str) -> str:
    return ATTRIBUTE_LABELS.get(key, key.replace("_", " "))


def _display_attribute_value(key: str, value: object) -> str:
    if isinstance(value, bool):
        return "var" if value else "yok"
    raw = str(value).strip()
    normalized = _normalize(raw)
    display = ATTRIBUTE_VALUE_LABELS.get(normalized, raw)
    if key == "guc_watt" and raw and "w" not in normalized:
        return f"{display} W"
    if key == "hazne_litre" and raw and "l" not in normalized:
        return f"{display} L"
    if key == "pil_suresi_saat" and raw and "saat" not in normalized:
        return f"{display} saat"
    return display


def _display_attribute_pair(key: str, value: object) -> str:
    return f"{_display_attribute_key(key)}: {_display_attribute_value(key, value)}"


def _clean_dict(value: dict | None) -> dict:
    return value or {}


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


@dataclass(slots=True)
class ProductMatch:
    product: DemoProduct
    score: int
    reason: str


@dataclass(slots=True)
class ProductMatchResult:
    products: list[DemoProduct]
    reason: str
    score: int
    explicit_product_mention: bool
    top_candidates: list[dict]
    product_id_source: str = ""
    alias_type_match_source: str = ""
    selected_group: dict | None = None
    candidate_groups: list[dict] | None = None


class ProductContextService:
    def __init__(self) -> None:
        self._last_product_match = ProductMatchResult([], "not_applicable", 0, False, [])
        self._embedding_service = get_embedding_service()

    async def _load_state(
        self, session: AsyncSession, conversation: Conversation | None
    ) -> ConversationState | None:
        if conversation is None:
            return None
        return await session.scalar(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation.id
            )
        )

    async def update_state(
        self,
        session: AsyncSession,
        conversation: Conversation | None,
        *,
        last_topic: str = "",
        last_product_id: int | None = None,
        last_product_name: str = "",
        last_order_id: int | None = None,
        last_order_no: str = "",
        last_return_id: int | None = None,
        last_cart_id: int | None = None,
        last_payment_id: int | None = None,
        last_intent: str = "",
        last_action: str = "",
        last_suggested_action: str = "",
        last_mentioned_product_ids: list[int] | None = None,
        last_mentioned_order_ids: list[int] | None = None,
        state_metadata: dict | None = None,
    ) -> None:
        if conversation is None:
            return
        state = await self._load_state(session, conversation)
        if state is None:
            state = ConversationState(conversation_id=conversation.id)
            session.add(state)
        if last_topic:
            state.last_topic = last_topic
        if last_product_id is not None:
            state.last_product_id = last_product_id
        if last_product_name:
            state.last_product_name = last_product_name
        if last_order_id is not None:
            state.last_order_id = last_order_id
        if last_order_no:
            state.last_order_no = last_order_no
        if last_return_id is not None:
            state.last_return_id = last_return_id
        if last_cart_id is not None:
            state.last_cart_id = last_cart_id
        if last_payment_id is not None:
            state.last_payment_id = last_payment_id
        if last_intent:
            state.last_intent = last_intent
        if last_action:
            state.last_action = last_action
        if last_suggested_action:
            state.last_suggested_action = last_suggested_action
        if last_mentioned_product_ids is not None:
            state.last_mentioned_product_ids = last_mentioned_product_ids
        if last_mentioned_order_ids is not None:
            state.last_mentioned_order_ids = last_mentioned_order_ids
        if state_metadata is not None:
            state.state_metadata = state_metadata

    def _detect_route_mode(self, category: str, canonical_query: str) -> str:
        query = _normalize(canonical_query)
        if not query:
            return "fallback_unclear"
        has_product = _contains_any(query, PRODUCT_HINTS)
        has_support = _contains_any(query, SUPPORT_HINTS) or bool(
            re.search(r"\bDMO-\d+-\d+\b", query, flags=re.IGNORECASE)
        )
        if "favori" in query or "yorum" in query or "puan" in query:
            return "review_favorite_mixed" if has_support else "product_only"
        if "kupon" in query or "sepet" in query or "kampanya" in query:
            return "cart_coupon_mixed"
        if (
            ("siparis" in query or "sipariş" in query)
            and any(term in query for term in ("olusmad", "oluşmad", "gorunm", "görünm", "yok"))
        ):
            return "payment_account_mixed"
        if "kart" in query or "cüzdan" in query or "wallet" in query or "bakiye" in query:
            return "product_support_mixed" if has_product else "payment_account_mixed"
        if ("iade" in query or "return" in query or "refund" in query) and "kod" in query:
            return "return_refund_mixed"
        if "iade" in query or "refund" in query or "return" in query:
            return "product_support_mixed" if has_product else (
                "return_refund_mixed" if has_support else "support_only"
            )
        if "sipariş" in query or re.search(r"\bDMO-\d+-\d+\b", query, flags=re.IGNORECASE):
            return "order_product_mixed" if has_product else "support_only"
        if has_product and has_support:
            return "product_support_mixed"
        if has_product:
            return "product_only"
        if has_support:
            return "support_only"
        if category in {"SIPARIS", "IADE", "ODEME", "KARGO_TESLIMAT", "KAMPANYA_PUAN"}:
            return "support_only"
        return "fallback_unclear"

    def _looks_like_followup(self, query: str) -> bool:
        normalized = _normalize(query)
        if not normalized:
            return False
        if "nereden" in normalized:
            return False
        if re.search(r"\bDMO-\d+-\d+\b", normalized, flags=re.IGNORECASE):
            return False
        return any(term in normalized for term in FOLLOWUP_HINTS)

    def _looks_like_correction(self, query: str) -> bool:
        normalized = _normalize(query)
        if not normalized:
            return False
        return any(term in normalized for term in CORRECTION_HINTS)

    def _query_tokens(self, query: str) -> list[str]:
        normalized = _normalize(query)
        tokens = [
            token
            for token in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", normalized)
            if token and token not in QUERY_STOPWORDS and len(token) > 1
        ]
        return tokens

    def _product_name_tokens(self, product: DemoProduct) -> list[str]:
        return [
            token
            for token in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", _normalize(product.name))
            if token and token not in QUERY_STOPWORDS
        ]

    def _candidate_debug(self, scored: list[ProductMatch]) -> list[dict]:
        return [
            {
                "product_id": item.product.id,
                "sku": item.product.sku,
                "name": item.product.name,
                "score": item.score,
                "reason": item.reason,
            }
            for item in scored[:5]
        ]

    @staticmethod
    def _alias_phrase_matches(normalized_query: str, normalized_alias: str) -> bool:
        if not normalized_alias:
            return False
        if normalized_query == normalized_alias:
            return True
        return re.search(
            rf"(^|\s){re.escape(normalized_alias)}(\s|$)",
            normalized_query,
        ) is not None

    def _alias_candidate_debug(self, aliases: list[DemoProductAlias]) -> list[dict]:
        return [
            {
                "alias_id": alias.id,
                "alias": alias.alias,
                "alias_type": alias.alias_type,
                "product_id": alias.product_id,
                "category": alias.category,
                "subcategory": alias.subcategory,
                "priority": alias.priority,
            }
            for alias in aliases[:5]
        ]

    async def _selected_products_by_alias(
        self,
        session: AsyncSession,
        query: str,
    ) -> list[DemoProduct]:
        normalized = _normalize(query)
        if not normalized:
            return []
        aliases = (
            await session.scalars(
                select(DemoProductAlias)
                .where(DemoProductAlias.is_active.is_(True))
                .order_by(
                    func.length(DemoProductAlias.normalized_alias).desc(),
                    DemoProductAlias.priority.desc(),
                    DemoProductAlias.id.asc(),
                )
            )
        ).all()
        matched_aliases = [
            alias
            for alias in aliases
            if self._alias_phrase_matches(normalized, alias.normalized_alias)
        ]
        if not matched_aliases:
            return []

        product_aliases = [
            alias
            for alias in matched_aliases
            if alias.alias_type == "PRODUCT" and alias.product_id is not None
        ]
        if product_aliases:
            alias = product_aliases[0]
            product = await session.scalar(
                select(DemoProduct).where(
                    DemoProduct.id == alias.product_id,
                    DemoProduct.is_active.is_(True),
                )
            )
            if product is None:
                return []
            self._last_product_match = ProductMatchResult(
                [product],
                "product_alias_match",
                98,
                True,
                self._candidate_debug([ProductMatch(product, 98, "product_alias_match")]),
                product_id_source="alias_product",
                alias_type_match_source="PRODUCT",
            )
            return [product]

        group_aliases = [
            alias for alias in matched_aliases if alias.alias_type == "PRODUCT_GROUP"
        ]
        if not group_aliases:
            return []
        alias = group_aliases[0]
        statement = select(DemoProduct).where(DemoProduct.is_active.is_(True))
        if alias.category:
            statement = statement.where(DemoProduct.category == alias.category)
        if alias.subcategory:
            statement = statement.where(DemoProduct.subcategory == alias.subcategory)
        products = (
            await session.scalars(
                statement.order_by(DemoProduct.name.asc()).limit(8)
            )
        ).all()
        if not products:
            return []
        selected_group = {
            "alias": alias.alias,
            "category": alias.category,
            "subcategory": alias.subcategory,
            "product_count": len(products),
        }
        self._last_product_match = ProductMatchResult(
            list(products),
            "product_group_alias_match",
            92,
            True,
            self._candidate_debug(
                [ProductMatch(product, 92, "product_group_alias_match") for product in products]
            ),
            product_id_source="alias_group",
            alias_type_match_source="PRODUCT_GROUP",
            selected_group=selected_group,
            candidate_groups=self._alias_candidate_debug(group_aliases),
        )
        return list(products)

    @staticmethod
    def _product_search_text(product: DemoProduct) -> str:
        attribute_text = " ".join(
            f"{key} {value}" for key, value in (product.attributes or {}).items()
        )
        tag_text = " ".join(product.tags or [])
        return " ".join(
            part
            for part in [
                product.name,
                product.sku,
                product.brand,
                product.category,
                product.subcategory,
                product.description,
                product.search_text,
                product.ai_context,
                tag_text,
                attribute_text,
            ]
            if part
        )

    def _semantic_score(self, query: str, product: DemoProduct) -> float:
        try:
            query_vector = self._embedding_service.embed_query(query)
            product_vector = self._embedding_service.embed_query(
                self._product_search_text(product)
            )
        except Exception:
            return 0.0
        return _cosine_similarity(query_vector, product_vector)

    async def _product_stats(
        self,
        session: AsyncSession,
        product_ids: list[int],
        user: User | None = None,
    ) -> dict[int, dict]:
        if not product_ids:
            return {}
        stats = {
            product_id: {
                "rating_average": None,
                "review_count": 0,
                "rating_distribution": {},
                "positive_review_count": 0,
                "negative_review_count": 0,
                "favorite_count": 0,
                "is_favorited": False,
            }
            for product_id in product_ids
        }
        review_rows = (
            await session.execute(
                select(
                    DemoProductReview.product_id,
                    func.avg(DemoProductReview.rating),
                    func.count(DemoProductReview.id),
                )
                .where(
                    DemoProductReview.product_id.in_(product_ids),
                    DemoProductReview.is_visible.is_(True),
                )
                .group_by(DemoProductReview.product_id)
            )
        ).all()
        for product_id, rating_average, review_count in review_rows:
            stats[product_id]["rating_average"] = (
                Decimal(str(rating_average)).quantize(Decimal("0.01"))
                if rating_average is not None
                else None
            )
            stats[product_id]["review_count"] = review_count
        favorite_rows = (
            await session.execute(
                select(DemoProductFavorite.product_id, func.count(DemoProductFavorite.id))
                .where(DemoProductFavorite.product_id.in_(product_ids))
                .group_by(DemoProductFavorite.product_id)
            )
        ).all()
        for product_id, favorite_count in favorite_rows:
            stats[product_id]["favorite_count"] = favorite_count
        if user is not None:
            favorited = (
                await session.scalars(
                    select(DemoProductFavorite.product_id).where(
                        DemoProductFavorite.product_id.in_(product_ids),
                        DemoProductFavorite.user_id == user.id,
                    )
                )
            ).all()
            for product_id in favorited:
                stats[product_id]["is_favorited"] = True
        review_rows = (
            await session.execute(
                select(
                    DemoProductReview.product_id,
                    DemoProductReview.rating,
                    DemoProductReview.title,
                    DemoProductReview.body,
                )
                .where(
                    DemoProductReview.product_id.in_(product_ids),
                    DemoProductReview.is_visible.is_(True),
                )
                .order_by(DemoProductReview.created_at.desc())
            )
        ).all()
        for product_id, rating, title, body in review_rows:
            if rating is not None:
                bucket = str(int(rating))
                distribution = stats[product_id].setdefault("rating_distribution", {})
                distribution[bucket] = int(distribution.get(bucket, 0)) + 1
                if int(rating) >= 4:
                    stats[product_id]["positive_review_count"] += 1
                elif int(rating) <= 2:
                    stats[product_id]["negative_review_count"] += 1
            samples = stats[product_id].setdefault("review_samples", [])
            if len(samples) < 3:
                review_text = " - ".join(
                    part for part in [str(title or "").strip(), str(body or "").strip()] if part
                )
                if review_text:
                    samples.append({"rating": rating, "text": review_text})
        return stats

    @staticmethod
    def _product_evidence_data(product: DemoProduct, stats: dict) -> dict:
        return {
            "name": product.name,
            "sku": product.sku,
            "brand": product.brand,
            "category": product.category,
            "subcategory": product.subcategory,
            "description": product.description,
            "search_text": product.search_text,
            "ai_context": product.ai_context,
            "tags": product.tags,
            "attributes": product.attributes,
            "price": product.price,
            "currency": product.currency,
            "stock": product.stock,
            "returnable": product.returnable,
            "return_policy_note": product.return_policy_note,
            "warranty_months": product.warranty_months,
            "warranty_note": product.warranty_note,
            "rating_average": stats.get("rating_average"),
            "review_count": stats.get("review_count", 0),
        }

    @staticmethod
    def _review_evidence_data(stats: dict) -> dict:
        reviews = [
            {
                "rating": sample.get("rating"),
                "title": "",
                "body": sample.get("text", ""),
                "verified": None,
            }
            for sample in (stats.get("review_samples") or [])
            if isinstance(sample, dict)
        ]
        return {
            "rating_average": stats.get("rating_average"),
            "review_count": stats.get("review_count", 0),
            "rating_distribution": stats.get("rating_distribution") or {},
            "positive_review_count": stats.get("positive_review_count", 0),
            "negative_review_count": stats.get("negative_review_count", 0),
            "sample_reviews": reviews[:3],
            "reviews": reviews[:3],
        }

    def _product_line(self, product: DemoProduct, stats: dict) -> str:
        attributes = _clean_dict(product.attributes)
        attribute_preview = ", ".join(
            _display_attribute_pair(key, value)
            for key, value in list(attributes.items())[:5]
            if str(value).strip()
        )
        parts = [
            f"{product.name} ({product.sku})",
            f"kategori bilgisi={product.category}/{product.subcategory or '-'}",
            f"marka={product.brand or '-'}",
            f"fiyat={product.price} {product.currency}",
            f"stok={product.stock}",
        ]
        if stats.get("rating_average") is not None:
            parts.append(
                f"puan={stats['rating_average']} / 5 ({stats.get('review_count', 0)} yorum)"
            )
        if stats.get("favorite_count"):
            parts.append(f"favori sayısı={stats['favorite_count']}")
        if product.returnable is not None:
            parts.append(f"iade edilebilir={'evet' if product.returnable else 'hayır'}")
        if product.warranty_months is not None:
            parts.append(f"garanti={product.warranty_months} ay")
        if product.description:
            parts.append(f"açıklama={product.description}")
        if product.ai_context:
            parts.append(f"detay={product.ai_context}")
        if attribute_preview:
            parts.append(f"özellikler={attribute_preview}")
        if stats.get("review_samples"):
            sample_text = []
            for sample in stats["review_samples"]:
                if isinstance(sample, dict):
                    rating = sample.get("rating")
                    text = sample.get("text")
                    sample_text.append(f"{rating}/5: {text}" if rating is not None else str(text))
                elif sample:
                    sample_text.append(str(sample))
            parts.append(f"yorum özeti={' | '.join(sample_text)}")
        return "; ".join(parts)

    async def _selected_products(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        selected_product_id: int | None = None,
        product_id_source: str = "current_product_id",
    ) -> list[DemoProduct]:
        self._last_product_match = ProductMatchResult([], "not_applicable", 0, False, [])
        statement = select(DemoProduct).where(DemoProduct.is_active.is_(True))
        if selected_product_id is not None:
            statement = statement.where(DemoProduct.id == selected_product_id)
            product = await session.scalar(statement)
            if product:
                self._last_product_match = ProductMatchResult(
                    [product],
                    "trusted_context_match",
                    100,
                    False,
                    [],
                    product_id_source=product_id_source,
                )
            return [product] if product else []
        normalized = _normalize(query)
        terms = self._query_tokens(query)
        if not terms:
            self._last_product_match = ProductMatchResult([], "no_product_mention", 0, False, [])
            return []
        rows = (
            await session.scalars(
                statement.limit(200)
            )
        ).all()
        explicit_scored: list[ProductMatch] = []
        weak_scored: list[ProductMatch] = []
        for product in rows:
            name_haystack = _normalize(product.name)
            sku_haystack = _normalize(product.sku)
            haystack = _normalize(
                " ".join(
                    [
                        product.name,
                        product.brand,
                        product.category,
                        product.subcategory,
                        product.description,
                        product.search_text,
                        product.ai_context,
                        " ".join(product.tags or []),
                        " ".join(f"{k} {v}" for k, v in (product.attributes or {}).items()),
                    ]
                )
            )
            name_tokens = self._product_name_tokens(product)
            haystack_tokens = [
                token
                for token in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", haystack)
                if token
            ]
            score = 0
            reason = ""
            if sku_haystack and sku_haystack in normalized:
                score = 130
                reason = "sku_contains"
            elif name_haystack and name_haystack in normalized:
                score = 120
                reason = "name_contains"
            elif name_haystack and normalized == name_haystack:
                score = 120
                reason = "name_exact"
            else:
                matched_name_tokens = [
                    token
                    for token in name_tokens
                    if any(_token_matches(term, token) for term in terms)
                ]
                coverage = len(set(matched_name_tokens)) / len(set(name_tokens)) if name_tokens else 0
                numeric_bonus = sum(
                    12
                    for token in name_tokens
                    if any(char.isdigit() for char in token)
                    and any(_token_matches(term, token) for term in terms)
                )
                if coverage >= 0.75 and matched_name_tokens:
                    score = int(coverage * 90) + numeric_bonus
                    reason = "name_token_coverage"
            if score:
                explicit_scored.append(ProductMatch(product=product, score=score, reason=reason))
                continue

            weak_score = 0
            for term in terms:
                if term and any(_token_matches(term, token) for token in haystack_tokens):
                    weak_score += 1
            if weak_score >= 2:
                weak_scored.append(
                    ProductMatch(product=product, score=weak_score, reason="weak_haystack")
                )

        explicit_scored.sort(
            key=lambda item: (-item.score, item.product.category, item.product.name)
        )
        if explicit_scored:
            top_score = explicit_scored[0].score
            close = [item for item in explicit_scored if top_score - item.score <= 8]
            if len(close) > 1:
                self._last_product_match = ProductMatchResult(
                    [],
                    "ambiguous_catalog_match",
                    top_score,
                    True,
                    self._candidate_debug(close),
                )
                return []
            self._last_product_match = ProductMatchResult(
                [explicit_scored[0].product],
                "explicit_catalog_match",
                explicit_scored[0].score,
                True,
                self._candidate_debug(explicit_scored),
                product_id_source="explicit_fuzzy",
            )
            return [explicit_scored[0].product]

        weak_scored.sort(key=lambda item: (-item.score, item.product.category, item.product.name))
        if weak_scored:
            top_score = weak_scored[0].score
            close = [item for item in weak_scored if top_score - item.score <= 1]
            if len(close) > 1:
                self._last_product_match = ProductMatchResult(
                    [],
                    "ambiguous_weak_match",
                    top_score,
                    False,
                    self._candidate_debug(close),
                )
                return []
            if top_score < 3:
                self._last_product_match = ProductMatchResult(
                    [], "no_catalog_match", 0, bool(terms), self._candidate_debug(weak_scored)
                )
                return []
            self._last_product_match = ProductMatchResult(
                [weak_scored[0].product],
                "weak_catalog_match",
                weak_scored[0].score,
                False,
                self._candidate_debug(weak_scored),
                product_id_source="explicit_fuzzy",
            )
            return [weak_scored[0].product]

        candidates = explicit_scored or weak_scored
        self._last_product_match = ProductMatchResult(
            [], "no_catalog_match", 0, bool(terms), self._candidate_debug(candidates)
        )
        return []

    async def _selected_products_hybrid(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        selected_product_id: int | None = None,
    ) -> list[DemoProduct]:
        alias_products = await self._selected_products_by_alias(session, query)
        if alias_products:
            return alias_products

        primary_products = await self._selected_products(
            session,
            user,
            query,
        )
        primary_match = self._last_product_match
        if primary_products:
            return primary_products
        if primary_match.reason in {
            "ambiguous_catalog_match",
            "ambiguous_weak_match",
            "ambiguous_semantic_match",
        }:
            return []
        if not primary_match.top_candidates:
            if selected_product_id is not None:
                return await self._selected_products(
                    session,
                    user,
                    query,
                    selected_product_id=selected_product_id,
                )
            self._last_product_match = primary_match
            return primary_products

        normalized = _normalize(query)
        terms = self._query_tokens(query)
        if not terms:
            return primary_products

        rows = (
            await session.scalars(
                select(DemoProduct).where(DemoProduct.is_active.is_(True)).limit(200)
            )
        ).all()
        if not rows:
            return primary_products

        scored: list[ProductMatch] = []
        for product in rows:
            haystack = _normalize(self._product_search_text(product))
            fuzzy_ratio = SequenceMatcher(None, normalized, haystack).ratio()
            token_overlap = sum(
                1
                for term in terms
                if term and any(_token_matches(term, token) for token in haystack.split())
            )
            semantic_score = self._semantic_score(normalized, product)
            score = max(
                int(fuzzy_ratio * 100),
                35 + token_overlap * 5,
                int(semantic_score * 100),
            )
            if score >= 45:
                reason = "semantic_match" if semantic_score >= 0.55 else "fuzzy_text_match"
                scored.append(ProductMatch(product=product, score=score, reason=reason))

        scored.sort(key=lambda item: (-item.score, item.product.category, item.product.name))
        if not scored:
            self._last_product_match = primary_match
            return primary_products

        top_score = scored[0].score
        close = [item for item in scored if top_score - item.score <= 5]
        if len(close) > 1 or top_score < 70:
            self._last_product_match = ProductMatchResult(
                [],
                "ambiguous_semantic_match" if len(close) > 1 else "low_confidence_fuzzy_candidates",
                top_score,
                True,
                self._candidate_debug(close),
                product_id_source="explicit_fuzzy",
            )
            return []

        self._last_product_match = ProductMatchResult(
            [scored[0].product],
            scored[0].reason,
            scored[0].score,
            False,
            self._candidate_debug(scored),
            product_id_source="explicit_fuzzy",
        )
        return [scored[0].product]

    async def _selected_orders(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        selected_order_no: str | None = None,
        selected_order_id: int | None = None,
    ) -> list[DemoOrder]:
        statement = (
            select(DemoOrder)
            .options(
                selectinload(DemoOrder.items),
                selectinload(DemoOrder.shipment),
                selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
            )
            .where(DemoOrder.user_id == user.id)
            .order_by(DemoOrder.updated_at.desc())
        )
        if selected_order_id is not None:
            statement = statement.where(DemoOrder.id == selected_order_id)
        elif selected_order_no:
            statement = statement.where(DemoOrder.order_no == selected_order_no)
        elif match := re.search(r"\bDMO-\d+-\d+\b", query, flags=re.IGNORECASE):
            statement = statement.where(DemoOrder.order_no == match.group(0).upper())
        else:
            statement = statement.limit(3)
        return (await session.scalars(statement)).all()

    def _order_line(self, order: DemoOrder) -> str:
        shipment = order.shipment
        return_request = order.return_request
        first_item = order.items[0] if order.items else None
        parts = [
            f"{order.order_no} numaralı sipariş",
            f"durum={order.order_status}",
            f"ödeme={order.payment_status}",
            f"kargo={order.shipping_status}",
        ]
        if first_item:
            parts.append(f"ürün={first_item.product_name}")
        if shipment and shipment.tracking_number:
            parts.append(f"takip={shipment.tracking_number}")
        if return_request:
            parts.append(
                f"iade={return_request.return_status}/{return_request.refund_status}"
            )
        return "; ".join(parts)

    def _coupon_line(self, coupon: DemoCoupon, cart: DemoCart | None) -> str:
        if cart is None:
            return ""
        return (
            f"Kupon {coupon.code}: durum={coupon.status}; indirim="
            f"{coupon.discount_value} {coupon.discount_type}; min sepet={coupon.min_cart_total}; "
            f"kategori={coupon.allowed_category or 'tümü'}; sepet={cart.total}"
        )

    async def _active_cart(
        self, session: AsyncSession, user: User, selected_cart_id: int | None = None
    ) -> DemoCart | None:
        statement = (
            select(DemoCart)
            .options(selectinload(DemoCart.items).selectinload(DemoCartItem.product))
            .where(DemoCart.user_id == user.id, DemoCart.status == "ACTIVE")
            .order_by(DemoCart.id.desc())
        )
        if selected_cart_id is not None:
            statement = statement.where(DemoCart.id == selected_cart_id)
        return await session.scalar(statement)

    async def _selected_returns(
        self,
        session: AsyncSession,
        user: User,
        *,
        selected_return_id: int | None = None,
        selected_order_id: int | None = None,
        limit: int = 2,
    ) -> list[DemoReturnRequest]:
        statement = (
            select(DemoReturnRequest)
            .options(
                selectinload(DemoReturnRequest.refund),
                selectinload(DemoReturnRequest.order),
            )
            .where(DemoReturnRequest.user_id == user.id)
            .order_by(DemoReturnRequest.updated_at.desc())
        )
        if selected_return_id is not None:
            statement = statement.where(DemoReturnRequest.id == selected_return_id)
        elif selected_order_id is not None:
            statement = statement.where(DemoReturnRequest.order_id == selected_order_id)
        else:
            statement = statement.limit(limit)
        return (await session.scalars(statement)).all()

    async def _selected_payment(
        self,
        session: AsyncSession,
        user: User,
        selected_payment_id: int | None = None,
        canonical_query: str = "",
    ) -> DemoPaymentAttempt | None:
        if selected_payment_id is not None:
            return await session.scalar(
                select(DemoPaymentAttempt).where(
                    DemoPaymentAttempt.user_id == user.id,
                    DemoPaymentAttempt.id == selected_payment_id,
                )
            )
        query = _normalize(canonical_query)
        no_order_payment = (
            ("siparis" in query or "sipariş" in query)
            and any(term in query for term in ("olusmad", "oluşmad", "gorunm", "görünm", "yok"))
        ) or any(
            term in query
            for term in (
                "para cekil",
                "para cekildi",
                "kartımdan cekil",
                "kartimdan cekil",
                "odeme al",
                "ödeme al",
            )
        )
        if not no_order_payment:
            return None
        return await session.scalar(
            select(DemoPaymentAttempt)
            .where(
                DemoPaymentAttempt.user_id == user.id,
                DemoPaymentAttempt.status == "CAPTURED_NO_ORDER",
            )
            .order_by(DemoPaymentAttempt.created_at.desc())
            .limit(1)
        )

    async def build(
        self,
        session: AsyncSession,
        user: User,
        category: str,
        canonical_query: str,
        *,
        conversation: Conversation | None = None,
        selected_order_no: str | None = None,
        frontend_context: dict | None = None,
        original_query: str | None = None,
        allow_alias_probe: bool = False,
    ) -> dict:
        state = await self._load_state(session, conversation)
        context_query = f"{canonical_query} {original_query or ''}".strip()
        frontend_context = frontend_context or {}
        current_product_id = _positive_int(frontend_context.get("current_product_id"))
        current_order_id = _positive_int(frontend_context.get("current_order_id"))
        current_cart_id = _positive_int(frontend_context.get("current_cart_id"))
        current_return_id = _positive_int(frontend_context.get("current_return_id"))
        current_payment_id = _positive_int(frontend_context.get("current_payment_id"))
        page_context = str(frontend_context.get("page_context") or "").strip()
        route_mode = self._detect_route_mode(category, context_query)
        is_followup = self._looks_like_followup(context_query)
        is_correction = self._looks_like_correction(context_query)
        if page_context == "product" and current_product_id and route_mode in {
            "fallback_unclear",
            "support_only",
            "product_only",
        }:
            route_mode = "product_only"
        if page_context == "cart" and route_mode in {"fallback_unclear", "support_only"}:
            route_mode = "cart_coupon_mixed"
        if page_context == "returns" and route_mode in {"fallback_unclear", "support_only"}:
            route_mode = "return_refund_mixed"
        if current_order_id and route_mode in {"fallback_unclear", "support_only"} and is_followup:
            route_mode = "order_product_mixed"
        if state and is_followup:
            if route_mode in {"support_only", "product_only", "fallback_unclear"}:
                route_mode = "followup_resolved"
        product_context_modes = {
            "product_only",
            "product_support_mixed",
            "review_favorite_mixed",
            "cart_coupon_mixed",
            "order_product_mixed",
            "return_refund_mixed",
            "followup_resolved",
        }
        selected_product_id = current_product_id
        canonical_product_id = current_product_id
        canonical_product_source = "current_product_id" if current_product_id else ""
        product_group_suppressed_reason = (
            "canonical_product_id" if canonical_product_id else ""
        )
        fuzzy_suppressed_reason = ""
        conflicting_product_ids: list[int] = []
        followup_product_id = (
            state.last_product_id if state and is_followup and not is_correction else None
        )
        selected_order_id = current_order_id or (state.last_order_id if state and is_followup else None)
        selected_cart_id = current_cart_id or (state.last_cart_id if state and is_followup else None)
        selected_return_id = current_return_id or (state.last_return_id if state and is_followup else None)
        selected_payment_id = current_payment_id or (
            state.last_payment_id if state and is_followup else None
        )
        selected_order_no = selected_order_no or (state.last_order_no if state else None)
        selected_products: list[DemoProduct] = []
        selected_orders: list[DemoOrder] = []
        cart: DemoCart | None = None
        coupon: DemoCoupon | None = None
        wallet: DemoWallet | None = None
        security: DemoUserSecurityProfile | None = None
        saved_cards: list[DemoSavedCard] = []
        returns: list[DemoReturnRequest] = []
        selected_payment: DemoPaymentAttempt | None = None
        product_match_reason = "not_applicable"
        product_match_score = 0
        explicit_product_mention = False
        top_candidates: list[dict] = []
        rejected_candidates: list[dict] = []
        match_result = ProductMatchResult([], "not_applicable", 0, False, [])

        if route_mode in product_context_modes:
            if canonical_product_id is not None:
                selected_products = await self._selected_products(
                    session,
                    user,
                    context_query,
                    selected_product_id=canonical_product_id,
                    product_id_source=canonical_product_source,
                )
            else:
                selected_products = await self._selected_products_hybrid(
                    session,
                    user,
                    context_query,
                )
            match_result = self._last_product_match
            product_match_reason = match_result.reason
            product_match_score = match_result.score
            explicit_product_mention = match_result.explicit_product_mention
            top_candidates = match_result.top_candidates
            if (
                not selected_products
                and match_result.reason in {"no_product_mention", "no_catalog_match"}
            ):
                fuzzy_suppressed_reason = "no_explicit_product_candidate"
            elif match_result.reason == "low_confidence_fuzzy_candidates":
                fuzzy_suppressed_reason = "low_confidence"
            if selected_products:
                product_match_reason = match_result.reason
            elif is_correction and state and state.last_product_id is not None:
                rejected_candidates.append(
                    {
                        "product_id": state.last_product_id,
                        "reason": "conversation_state_contested",
                    }
                )
            elif followup_product_id is not None and not explicit_product_mention:
                canonical_product_id = followup_product_id
                canonical_product_source = "followup_state"
                product_group_suppressed_reason = "canonical_product_id"
                selected_products = await self._selected_products(
                    session,
                    user,
                    context_query,
                    selected_product_id=followup_product_id,
                    product_id_source="followup_state",
                )
                if selected_products:
                    match_result = self._last_product_match
                    product_match_reason = "followup_state"
                    product_match_score = match_result.score
                    top_candidates = match_result.top_candidates
            elif route_mode == "product_only":
                product_match_reason = (
                    product_match_reason
                    if product_match_reason
                    in {
                        "ambiguous_catalog_match",
                        "ambiguous_weak_match",
                        "no_catalog_match",
                        "no_product_mention",
                    }
                    else "clarification_needed"
                )

        if (
            allow_alias_probe
            and not selected_products
            and selected_product_id is None
            and canonical_product_id is None
        ):
            alias_probe_products = await self._selected_products_by_alias(
                session, context_query
            )
            if alias_probe_products:
                selected_products = alias_probe_products
                match_result = self._last_product_match
                product_match_reason = match_result.reason
                product_match_score = match_result.score
                explicit_product_mention = match_result.explicit_product_mention
                top_candidates = match_result.top_candidates
                product_context_modes = set(product_context_modes)
                product_context_modes.add(route_mode)

        if (
            is_correction
            and not selected_products
            and state
            and state.last_product_id is not None
            and not rejected_candidates
        ):
            rejected_candidates.append(
                {
                    "product_id": state.last_product_id,
                    "reason": "conversation_state_contested",
                }
            )

        clarification_needed = (
            route_mode in {"fallback_unclear", "product_only", "followup_resolved"}
            and not selected_products
        ) or product_match_reason in {
            "ambiguous_catalog_match",
            "ambiguous_weak_match",
            "ambiguous_semantic_match",
            "low_confidence_fuzzy_candidates",
            "clarification_needed",
        }

        if route_mode == "order_product_mixed" or selected_order_id or selected_order_no:
            selected_orders = await self._selected_orders(
                session,
                user,
                context_query,
                selected_order_no=selected_order_no,
                selected_order_id=selected_order_id,
            )
        elif route_mode == "return_refund_mixed" and selected_order_id:
            selected_orders = await self._selected_orders(
                session,
                user,
                canonical_query,
                selected_order_id=selected_order_id,
            )
        if route_mode == "cart_coupon_mixed" or selected_cart_id:
            cart = await self._active_cart(session, user, selected_cart_id)
            if cart and cart.coupon_code:
                coupon = await session.scalar(
                    select(DemoCoupon).where(DemoCoupon.code == cart.coupon_code)
                )
        if route_mode == "return_refund_mixed" or selected_return_id:
            returns = await self._selected_returns(
                session,
                user,
                selected_return_id=selected_return_id,
                selected_order_id=selected_order_id,
            )
        if route_mode in {"payment_account_mixed", "cart_coupon_mixed"}:
            wallet = await session.scalar(
                select(DemoWallet).where(DemoWallet.user_id == user.id)
            )
            saved_cards = (
                await session.scalars(
                    select(DemoSavedCard)
                    .where(
                        DemoSavedCard.user_id == user.id,
                        DemoSavedCard.is_active.is_(True),
                    )
                    .order_by(
                        DemoSavedCard.is_default.desc(),
                        DemoSavedCard.created_at.desc(),
                    )
                )
            ).all()
        selected_payment = await self._selected_payment(
            session, user, selected_payment_id, context_query
        )
        if route_mode == "payment_account_mixed":
            wallet = await session.scalar(
                select(DemoWallet).where(DemoWallet.user_id == user.id)
            )
            saved_cards = (
                await session.scalars(
                    select(DemoSavedCard)
                    .where(
                        DemoSavedCard.user_id == user.id,
                        DemoSavedCard.is_active.is_(True),
                    )
                    .order_by(
                        DemoSavedCard.is_default.desc(),
                        DemoSavedCard.created_at.desc(),
                    )
                )
            ).all()
            selected_payment = await self._selected_payment(
                session, user, selected_payment_id, context_query
            )
        if selected_payment is None:
            selected_payment = await self._selected_payment(
                session, user, selected_payment_id, context_query
            )
        if category == "HESAP_GUVENLIK" or "güvenlik" in _normalize(canonical_query):
            security = await session.scalar(
                select(DemoUserSecurityProfile).where(
                    DemoUserSecurityProfile.user_id == user.id
                )
            )

        product_stats = await self._product_stats(session, [p.id for p in selected_products], user)
        product_evidence = [
            {
                "product_id": product.id,
                "data": self._product_evidence_data(product, product_stats.get(product.id, {})),
            }
            for product in selected_products
        ]
        review_evidence = [
            {
                "product_id": product.id,
                "data": self._review_evidence_data(product_stats.get(product.id, {})),
            }
            for product in selected_products
        ]
        product_lines = [
            self._product_line(product, product_stats.get(product.id, {}))
            for product in selected_products
        ]
        order_lines = [self._order_line(order) for order in selected_orders]
        return_lines = []
        for item in returns:
            refund = item.refund
            return_lines.append(
                f"{item.order.order_no if item.order else item.order_id} için iade: "
                f"kod={item.return_code}; iade durumu={item.return_status}; "
                f"refund={item.refund_status}; takip={item.return_tracking_no or '-'}; "
                f"sebep={item.return_reason or '-'}"
                + (
                    f"; refund_ref={refund.refund_reference}; refund_tutar={refund.refund_amount}"
                    if refund
                    else ""
                )
            )
        payment_lines = []
        if selected_payment:
            linked = (
                f"sipariş={selected_payment.order_id}"
                if selected_payment.order_id
                else "siparişe bağlı değil"
            )
            payment_lines.append(
                f"Ödeme kaydı {selected_payment.provider_reference}: durum={selected_payment.status}; "
                f"tutar={selected_payment.amount}; bağlantı={linked}; açıklama={selected_payment.failure_reason or '-'}"
            )

        decision_hints: list[str] = []
        if route_mode == "product_only" and selected_products:
            decision_hints.append(
                "Ürünün teknik özellikleri ve iade/garanti notu birlikte değerlendirilmelidir."
            )
        if route_mode == "followup_resolved" and selected_products:
            decision_hints.append(
                "Kullanıcı önceki ürün için ek teknik detay istedi; aynı ürünü doğal dille detaylandır."
            )
        if route_mode in {"product_support_mixed", "return_refund_mixed"} and selected_products:
            decision_hints.append(
                "Ürün bilgisi ile destek politikası birlikte değerlendirilmelidir."
            )
        if route_mode == "cart_coupon_mixed":
            if cart is None:
                decision_hints.append("Aktif sepet bulunamadı.")
            elif not cart.items:
                decision_hints.append("Aktif sepet boş.")
            elif coupon is None and cart.coupon_code:
                decision_hints.append("Sepetteki kuponun durumu doğrulanamıyor.")
        if route_mode == "review_favorite_mixed" and selected_products:
            decision_hints.append("Ürün puanı, yorum sayısı ve favori durumu dikkate alınmalı.")
        if route_mode == "order_product_mixed" and selected_orders:
            decision_hints.append("Sipariş ve ürün durumu birlikte değerlendirilmelidir.")
        if route_mode == "return_refund_mixed" and returns:
            decision_hints.append("İade kodu, iade statüsü ve refund statüsü birlikte yorumlanmalı.")
        if security and security.security_status != "NORMAL":
            decision_hints.append(f"Güvenlik durumu: {security.security_status}.")
        if wallet and wallet.status != "ACTIVE":
            decision_hints.append(f"Cüzdan durumu: {wallet.status}.")
        if saved_cards:
            decision_hints.append(
                f"Kayıtlı kart sayısı: {len(saved_cards)}; varsayılan kart var={any(card.is_default for card in saved_cards)}."
            )
        if selected_payment and selected_payment.status == "CAPTURED_NO_ORDER":
            decision_hints.append(
                "Bu ödeme başarılı alınmış görünüyor ancak sipariş kaydıyla eşleşmiyor; kullanıcıya tekrar ödeme denetmek yerine destek/ödeme incelemesi öner."
            )

        if canonical_product_id is not None:
            conflicting_product_ids = [
                int(item["product_id"])
                for item in top_candidates
                if item.get("product_id") is not None
                and int(item["product_id"]) != canonical_product_id
            ]
        selected_group = (
            {}
            if canonical_product_id is not None
            else (match_result.selected_group or {})
        )
        candidate_groups = (
            []
            if canonical_product_id is not None
            else (match_result.candidate_groups or [])
        )
        answer_mode = (
            "PRODUCT_GROUP"
            if selected_group and match_result.alias_type_match_source == "PRODUCT_GROUP"
            else "SPECIFIC_PRODUCT"
            if selected_products
            else "CLARIFICATION"
        )

        text_parts = []
        if selected_products:
            text_parts.append("ÜRÜN BAĞLAMI:")
            text_parts.extend(product_lines)
        if selected_orders:
            text_parts.append("SİPARİŞ BAĞLAMI:")
            text_parts.extend(order_lines)
        if returns:
            text_parts.append("İADE / REFUND BAĞLAMI:")
            text_parts.extend(return_lines)
        if payment_lines:
            text_parts.append("ÖDEME BAĞLAMI:")
            text_parts.extend(payment_lines)
        if cart:
            cart_product_names = ", ".join(
                item.product.name for item in cart.items[:3] if item.product
            )
            text_parts.append(
                "SEPET BAĞLAMI: "
                f"ürünler={cart_product_names or '-'}; subtotal={cart.subtotal}; "
                f"indirim={cart.discount_total}; total={cart.total}; kupon={cart.coupon_code or '-'}"
            )
        if coupon:
            text_parts.append(self._coupon_line(coupon, cart) or "")
        if wallet:
            text_parts.append(
                f"CUZDAN BAĞLAMI: bakiye={wallet.balance}; durum={wallet.status}; para birimi={wallet.currency}"
            )
        if security:
            text_parts.append(
                f"GÜVENLİK BAĞLAMI: durum={security.security_status}; risk_notu={security.risk_note or '-'}"
            )

        context = {
            "route_mode": route_mode,
            "category": category,
            "context_type": (
                "clarification_needed"
                if route_mode in {"fallback_unclear", "product_only"} and not selected_products
                else "intent"
            ),
            "items": product_lines + order_lines + return_lines + payment_lines,
            "payment_items": payment_lines,
            "text": "\n".join(part for part in text_parts if part.strip()),
            "decision_hints": decision_hints,
            "product_match_reason": product_match_reason,
            "product_match_score": product_match_score,
            "explicit_product_mention": explicit_product_mention,
            "canonical_product_id": canonical_product_id,
            "canonical_product_source": canonical_product_source,
            "product_group_suppressed_reason": product_group_suppressed_reason,
            "fuzzy_suppressed_reason": fuzzy_suppressed_reason,
            "conflicting_product_ids": conflicting_product_ids,
            "explicit_product_candidates": top_candidates,
            "rejected_candidates": rejected_candidates,
            "is_followup": is_followup,
            "is_correction": is_correction,
            "clarification_needed": clarification_needed,
            "state_updated": bool(
                selected_products
                and not match_result.selected_group
                and match_result.product_id_source != "followup_state"
            ),
            "top_candidates": top_candidates,
            "product_id_source": match_result.product_id_source,
            "alias_type_match_source": match_result.alias_type_match_source,
            "selected_group": selected_group,
            "candidate_groups": candidate_groups,
            "selected_product": (
                {
                    "id": selected_products[0].id,
                    "sku": selected_products[0].sku,
                    "name": selected_products[0].name,
                }
                if selected_products and not selected_group
                else {}
            ),
            "answer_mode": answer_mode,
            "selected_counts": {
                "products": len(selected_products),
                "orders": len(selected_orders),
                "payments": 1 if selected_payment else 0,
                "cart": 1 if cart else 0,
                "returns": len(returns),
                "saved_cards": len(saved_cards),
            },
            "selected_product_ids": [product.id for product in selected_products],
            "selected_order_ids": [order.id for order in selected_orders],
            "selected_return_ids": [item.id for item in returns],
            "selected_payment_ids": [selected_payment.id] if selected_payment else [],
            "product_evidence": product_evidence,
            "review_evidence": review_evidence,
            "cart_summary": (
                {
                    "id": cart.id,
                    "item_count": len(cart.items),
                    "coupon_code": cart.coupon_code,
                    "subtotal": str(cart.subtotal),
                    "discount_total": str(cart.discount_total),
                    "total": str(cart.total),
                }
                if cart
                else {}
            ),
            "security_status": security.security_status if security else "",
        }

        if selected_products and not selected_group:
            context["primary_product"] = {
                "id": selected_products[0].id,
                "sku": selected_products[0].sku,
                "name": selected_products[0].name,
                "category": selected_products[0].category,
            }
        if selected_orders:
            context["primary_order"] = {
                "id": selected_orders[0].id,
                "order_no": selected_orders[0].order_no,
                "order_status": selected_orders[0].order_status,
                "shipping_status": selected_orders[0].shipping_status,
                "payment_status": selected_orders[0].payment_status,
            }
        if returns:
            context["primary_return"] = {
                "id": returns[0].id,
                "order_id": returns[0].order_id,
                "return_code": returns[0].return_code,
                "return_status": returns[0].return_status,
                "refund_status": returns[0].refund_status,
            }
        if cart:
            context["primary_cart"] = {
                "id": cart.id,
                "coupon_code": cart.coupon_code,
                "item_count": len(cart.items),
            }
        if selected_payment:
            context["primary_payment"] = {
                "id": selected_payment.id,
                "provider_reference": selected_payment.provider_reference,
                "status": selected_payment.status,
                "order_id": selected_payment.order_id,
            }

        if route_mode == "followup_resolved" and state:
            context["context_type"] = "followup"
        return context
