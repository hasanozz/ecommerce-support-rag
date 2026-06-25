from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

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
    DemoProduct,
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


PRODUCT_HINTS = {
    "çay",
    "kahve",
    "bardak",
    "kupa",
    "termos",
    "çanta",
    "çantası",
    "ayakkabı",
    "kulaklık",
    "blender",
    "sweatshirt",
    "mat",
    "filtre",
    "demlik",
    "saklama",
    "gram",
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


@dataclass(slots=True)
class ProductMatch:
    product: DemoProduct
    score: int


class ProductContextService:
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
        last_intent: str = "",
        last_action: str = "",
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
        if last_intent:
            state.last_intent = last_intent
        if last_action:
            state.last_action = last_action
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
            samples = stats[product_id].setdefault("review_samples", [])
            if len(samples) < 2:
                review_text = " - ".join(
                    part for part in [str(title or "").strip(), str(body or "").strip()] if part
                )
                if review_text:
                    samples.append(f"{rating}/5: {review_text}" if rating is not None else review_text)
        return stats

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
            parts.append(f"yorum özeti={' | '.join(stats['review_samples'])}")
        return "; ".join(parts)

    async def _selected_products(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        selected_product_id: int | None = None,
    ) -> list[DemoProduct]:
        statement = select(DemoProduct).where(DemoProduct.is_active.is_(True))
        if selected_product_id is not None:
            statement = statement.where(DemoProduct.id == selected_product_id)
            product = await session.scalar(statement)
            return [product] if product else []
        normalized = _normalize(query)
        terms = [term for term in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", normalized) if term]
        if not terms:
            return []
        rows = (await session.scalars(statement)).all()
        scored: list[ProductMatch] = []
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
            name_tokens = [
                token
                for token in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", name_haystack)
                if token
            ]
            haystack_tokens = [
                token
                for token in re.split(r"[^\wçğıöşüÇĞİÖŞÜ0-9]+", haystack)
                if token
            ]
            score = 0
            if sku_haystack and sku_haystack in _normalize(query):
                score += 100
            if name_haystack and (
                name_haystack in _normalize(query) or _normalize(query) in name_haystack
            ):
                score += 80
            for term in terms:
                if term and any(_token_matches(term, token) for token in name_tokens):
                    score += 10
                elif term and any(_token_matches(term, token) for token in haystack_tokens):
                    score += 1
            if score:
                scored.append(ProductMatch(product=product, score=score))
        scored.sort(key=lambda item: (-item.score, item.product.category, item.product.name))
        return [item.product for item in scored[:1]]

    async def _selected_orders(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        selected_order_no: str | None = None,
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
        if selected_order_no:
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

    async def _active_cart(self, session: AsyncSession, user: User) -> DemoCart | None:
        return await session.scalar(
            select(DemoCart)
            .options(selectinload(DemoCart.items).selectinload(DemoCartItem.product))
            .where(DemoCart.user_id == user.id, DemoCart.status == "ACTIVE")
            .order_by(DemoCart.id.desc())
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
    ) -> dict:
        state = await self._load_state(session, conversation)
        route_mode = self._detect_route_mode(category, canonical_query)
        if state and self._looks_like_followup(canonical_query):
            if route_mode in {"support_only", "product_only", "fallback_unclear"}:
                route_mode = "followup_resolved"
        product_context_modes = {
            "product_only",
            "product_support_mixed",
            "review_favorite_mixed",
            "cart_coupon_mixed",
            "followup_resolved",
        }
        selected_product_id = state.last_product_id if state else None
        selected_order_no = selected_order_no or (state.last_order_no if state else None)
        selected_products: list[DemoProduct] = []
        selected_orders: list[DemoOrder] = []
        cart: DemoCart | None = None
        coupon: DemoCoupon | None = None
        wallet: DemoWallet | None = None
        security: DemoUserSecurityProfile | None = None
        saved_cards: list[DemoSavedCard] = []
        returns: list[DemoReturnRequest] = []
        product_match_reason = "not_applicable"

        if route_mode in product_context_modes:
            selected_products = await self._selected_products(session, user, canonical_query)
            if selected_products:
                product_match_reason = "catalog_match"
            elif route_mode == "followup_resolved" and selected_product_id is not None:
                selected_products = await self._selected_products(
                    session, user, canonical_query, selected_product_id=selected_product_id
                )
                if selected_products:
                    product_match_reason = "followup_state"
            elif route_mode == "product_only":
                product_match_reason = "clarification_needed"

            if route_mode in {
                "product_support_mixed",
                "review_favorite_mixed",
                "cart_coupon_mixed",
            }:
                selected_orders = await self._selected_orders(
                    session, user, canonical_query, selected_order_no=selected_order_no
                )
                cart = await self._active_cart(session, user)
                if cart and cart.coupon_code:
                    coupon = await session.scalar(
                        select(DemoCoupon).where(DemoCoupon.code == cart.coupon_code)
                    )
                wallet = await session.scalar(
                    select(DemoWallet).where(DemoWallet.user_id == user.id)
                )
                security = await session.scalar(
                    select(DemoUserSecurityProfile).where(
                        DemoUserSecurityProfile.user_id == user.id
                    )
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
                returns = (
                    await session.scalars(
                        select(DemoReturnRequest)
                        .options(selectinload(DemoReturnRequest.refund))
                        .where(DemoReturnRequest.user_id == user.id)
                        .order_by(DemoReturnRequest.updated_at.desc())
                        .limit(3)
                    )
                ).all()

        product_stats = await self._product_stats(session, [p.id for p in selected_products], user)
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
            "items": product_lines + order_lines + return_lines,
            "text": "\n".join(part for part in text_parts if part.strip()),
            "decision_hints": decision_hints,
            "product_match_reason": product_match_reason,
            "selected_counts": {
                "products": len(selected_products),
                "orders": len(selected_orders),
                "payments": 0,
                "cart": 1 if cart else 0,
                "returns": len(returns),
                "saved_cards": len(saved_cards),
            },
            "selected_product_ids": [product.id for product in selected_products],
            "selected_order_ids": [order.id for order in selected_orders],
            "selected_return_ids": [item.id for item in returns],
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

        if selected_products:
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

        if route_mode == "followup_resolved" and state:
            context["context_type"] = "followup"
        return context
