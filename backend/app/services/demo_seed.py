from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
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


DEMO_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "demo"

SCENARIO_MARKERS = {
    "payment-captured-no-order": "SCENARIO:PAYMENT_CAPTURED_NO_ORDER",
    "order-not-shipped": "SCENARIO:ORDER_NOT_SHIPPED",
    "delivered-not-received": "SCENARIO:DELIVERED_NOT_RECEIVED",
    "returnable-product": "SCENARIO:RETURNABLE_PRODUCT",
    "non-returnable-product": "SCENARIO:NON_RETURNABLE_PRODUCT",
}
EXPIRED_COUPON_SCENARIO = "expired-coupon"


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_text_value(item) for item in value if _text_value(item))
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {_text_value(item)}" for key, item in value.items() if _text_value(item)
        )
    return str(value)


def _normalize_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^\w\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def build_product_search_text(payload: dict) -> str:
    parts = [
        payload.get("sku"),
        payload.get("name"),
        payload.get("brand"),
        payload.get("category"),
        payload.get("subcategory"),
        payload.get("description"),
        _text_value(payload.get("tags", [])),
        _text_value(payload.get("attributes", {})),
    ]
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def build_product_ai_context(payload: dict) -> str:
    lines = [
        f"Ürün: {payload.get('name', '')}",
        f"SKU: {payload.get('sku', '')}",
        f"Marka: {payload.get('brand', '')}",
        f"Kategori: {payload.get('category', '')}/{payload.get('subcategory', '')}",
        f"Fiyat: {payload.get('price', '')} {payload.get('currency', 'TRY')}",
        f"Stok: {payload.get('stock', 0)}",
        f"İade edilebilir: {'evet' if payload.get('returnable', True) else 'hayır'}",
    ]
    if payload.get("return_policy_note"):
        lines.append(f"İade notu: {payload['return_policy_note']}")
    if payload.get("warranty_months") is not None:
        lines.append(f"Garanti: {payload['warranty_months']} ay")
    if payload.get("warranty_note"):
        lines.append(f"Garanti notu: {payload['warranty_note']}")
    if payload.get("description"):
        lines.append(f"Açıklama: {payload['description']}")
    if payload.get("attributes"):
        lines.append(f"Teknik özellikler: {_text_value(payload['attributes'])}")
    if payload.get("tags"):
        lines.append(f"Etiketler: {_text_value(payload['tags'])}")
    return "\n".join(line for line in lines if line.strip())


class DemoSeedService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEMO_DATA_DIR

    def load_demo_json(self, filename: str) -> Any:
        path = self.data_dir / filename
        if not path.exists():
            return [] if filename.endswith("s.json") else {}
        return json.loads(path.read_text(encoding="utf-8"))

    async def seed_products(self, session: AsyncSession) -> int:
        rows = self.load_demo_json("products.json")
        count = 0
        for payload in rows:
            sku = str(payload["sku"]).strip()
            product = await session.scalar(select(DemoProduct).where(DemoProduct.sku == sku))
            values = {
                "sku": sku,
                "name": str(payload["name"]).strip(),
                "brand": str(payload.get("brand", "")).strip(),
                "category": str(payload["category"]).strip(),
                "subcategory": str(payload.get("subcategory", "")).strip(),
                "price": money(payload["price"]),
                "currency": str(payload.get("currency", "TRY")).strip() or "TRY",
                "stock": int(payload.get("stock", 0)),
                "is_active": bool(payload.get("is_active", True)),
                "image_url": str(payload.get("image_url", "")).strip(),
                "image_urls": payload.get("image_urls", []) or [],
                "description": str(payload.get("description", "")).strip(),
                "returnable": bool(payload.get("returnable", True)),
                "return_policy_note": str(payload.get("return_policy_note", "")).strip(),
                "warranty_months": payload.get("warranty_months"),
                "warranty_note": str(payload.get("warranty_note", "")).strip(),
                "tags": payload.get("tags", []) or [],
                "attributes": payload.get("attributes", {}) or {},
                "search_text": build_product_search_text(payload),
                "ai_context": build_product_ai_context(payload),
            }
            if product is None:
                session.add(DemoProduct(**values))
            else:
                for key, value in values.items():
                    setattr(product, key, value)
            count += 1
        await session.flush()
        return count

    async def seed_coupons(self, session: AsyncSession) -> int:
        rows = self.load_demo_json("coupons.json")
        now = datetime.now(UTC)
        count = 0
        for payload in rows:
            code = str(payload["code"]).strip().upper()
            coupon = await session.scalar(select(DemoCoupon).where(DemoCoupon.code == code))
            expires_at = payload.get("expires_at")
            if expires_at:
                parsed_expires_at = datetime.fromisoformat(str(expires_at))
            else:
                parsed_expires_at = now + timedelta(days=int(payload.get("expires_in_days", 30)))
            values = {
                "code": code,
                "status": str(payload.get("status", "VALID")).strip(),
                "discount_type": str(payload.get("discount_type", "PERCENT")).strip(),
                "discount_value": money(payload.get("discount_value", "0")),
                "min_cart_total": money(payload.get("min_cart_total", "0")),
                "allowed_category": str(payload.get("allowed_category", "")).strip(),
                "expires_at": parsed_expires_at,
                "is_active": bool(payload.get("is_active", True)),
            }
            if coupon is None:
                session.add(DemoCoupon(**values))
            else:
                for key, value in values.items():
                    setattr(coupon, key, value)
            count += 1
        await session.flush()
        return count

    async def _demo_reviewer_user(self, session: AsyncSession, payload: dict) -> User:
        email = str(payload["user_email"]).strip().casefold()
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            return user
        user = User(
            google_sub=f"demo-reviewer:{email}",
            email=email,
            display_name=str(payload.get("display_name", "Demo Kullanıcı")).strip(),
            is_admin=False,
        )
        session.add(user)
        await session.flush()
        return user

    async def seed_product_reviews(self, session: AsyncSession) -> int:
        rows = self.load_demo_json("product_reviews.json")
        count = 0
        for payload in rows:
            product = await session.scalar(
                select(DemoProduct).where(DemoProduct.sku == str(payload["sku"]).strip())
            )
            if product is None:
                continue
            user = await self._demo_reviewer_user(session, payload)
            review = await session.scalar(
                select(DemoProductReview).where(
                    DemoProductReview.product_id == product.id,
                    DemoProductReview.user_id == user.id,
                )
            )
            values = {
                "product_id": product.id,
                "user_id": user.id,
                "rating": payload.get("rating"),
                "title": str(payload.get("title", "")).strip(),
                "body": str(payload.get("body", "")).strip(),
                "is_verified_purchase": bool(payload.get("is_verified_purchase", False)),
                "is_visible": bool(payload.get("is_visible", True)),
            }
            if review is None:
                session.add(DemoProductReview(**values))
            else:
                for key, value in values.items():
                    setattr(review, key, value)
            count += 1
        await session.flush()
        return count

    async def seed_product_aliases(self, session: AsyncSession) -> int:
        rows = self.load_demo_json("product_aliases.json")
        products = (
            await session.scalars(select(DemoProduct).where(DemoProduct.is_active.is_(True)))
        ).all()
        product_by_sku = {product.sku: product for product in products}
        count = 0
        for payload in rows:
            alias = str(payload.get("alias", "")).strip()
            alias_type = str(payload.get("alias_type", "")).strip().upper()
            normalized_alias = _normalize_alias(alias)
            if not alias or alias_type not in {"PRODUCT", "PRODUCT_GROUP"}:
                continue
            product = product_by_sku.get(str(payload.get("sku", "")).strip())
            product_id = product.id if product is not None else None
            if alias_type == "PRODUCT" and product_id is None:
                continue
            row = await session.scalar(
                select(DemoProductAlias).where(
                    DemoProductAlias.normalized_alias == normalized_alias,
                    DemoProductAlias.alias_type == alias_type,
                )
            )
            values = {
                "alias": alias,
                "normalized_alias": normalized_alias,
                "alias_type": alias_type,
                "product_id": product_id,
                "category": str(payload.get("category", "")).strip(),
                "subcategory": str(payload.get("subcategory", "")).strip(),
                "priority": int(payload.get("priority", 100)),
                "source": str(payload.get("source", "demo_seed")).strip() or "demo_seed",
                "is_active": bool(payload.get("is_active", True)),
            }
            if row is None:
                session.add(DemoProductAlias(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            count += 1
        await session.flush()
        return count

    async def seed_catalog(self, session: AsyncSession) -> dict:
        products = await self.seed_products(session)
        coupons = await self.seed_coupons(session)
        reviews = await self.seed_product_reviews(session)
        aliases = await self.seed_product_aliases(session)
        return {
            "products": products,
            "coupons": coupons,
            "reviews": reviews,
            "aliases": aliases,
        }

    async def seed_demo_wallet(self, session: AsyncSession, user: User, payload: dict) -> None:
        wallet = await session.scalar(select(DemoWallet).where(DemoWallet.user_id == user.id))
        values = {
            "user_id": user.id,
            "balance": money(payload.get("balance", "0")),
            "currency": str(payload.get("currency", "TRY")).strip() or "TRY",
            "status": str(payload.get("status", "ACTIVE")).strip(),
        }
        if wallet is None:
            session.add(DemoWallet(**values))
        else:
            for key, value in values.items():
                setattr(wallet, key, value)

    async def seed_demo_security(
        self, session: AsyncSession, user: User, payload: dict
    ) -> None:
        profile = await session.scalar(
            select(DemoUserSecurityProfile).where(DemoUserSecurityProfile.user_id == user.id)
        )
        values = {
            "user_id": user.id,
            "security_status": str(payload.get("security_status", "NORMAL")).strip(),
            "suspicious_login_count": int(payload.get("suspicious_login_count", 0)),
            "email_verified_required": bool(payload.get("email_verified_required", False)),
            "phone_verified_required": bool(payload.get("phone_verified_required", False)),
            "password_change_recommended": bool(
                payload.get("password_change_recommended", False)
            ),
            "risk_note": str(payload.get("risk_note", "")).strip(),
        }
        if profile is None:
            session.add(DemoUserSecurityProfile(**values))
        else:
            for key, value in values.items():
                setattr(profile, key, value)

    async def seed_demo_saved_cards(
        self, session: AsyncSession, user: User, rows: list[dict]
    ) -> int:
        count = 0
        for payload in rows:
            token = str(payload.get("card_token", "")).strip()
            if not token:
                continue
            card = await session.scalar(
                select(DemoSavedCard).where(DemoSavedCard.card_token == token)
            )
            values = {
                "user_id": user.id,
                "card_token": token,
                "card_brand": str(payload.get("card_brand", "")).strip(),
                "last4": str(payload.get("last4", "")).strip()[-4:],
                "holder_name": str(payload.get("holder_name", "")).strip(),
                "is_default": bool(payload.get("is_default", False)),
                "is_active": bool(payload.get("is_active", True)),
                "expiry_month": int(payload.get("expiry_month", 12)),
                "expiry_year": int(payload.get("expiry_year", 2030)),
            }
            if card is None:
                session.add(DemoSavedCard(**values))
            else:
                for key, value in values.items():
                    setattr(card, key, value)
            count += 1
        return count

    async def seed_demo_return_requests(
        self, session: AsyncSession, user: User, orders: dict[str, DemoOrder], rows: list[dict]
    ) -> int:
        count = 0
        for payload in rows:
            order_ref = str(payload.get("order_ref", "")).strip()
            order_suffix = str(payload.get("order_no_suffix", "")).strip().zfill(3)
            order = orders.get(order_ref)
            if order is None and order_suffix:
                order = next(
                    (item for key, item in orders.items() if key.endswith(f"-{order_suffix}")),
                    None,
                )
            if order is None:
                continue
            return_request = await session.scalar(
                select(DemoReturnRequest).where(DemoReturnRequest.order_id == order.id)
            )
            values = {
                "order_id": order.id,
                "user_id": user.id,
                "return_request": str(payload.get("return_request", "CREATED")).strip(),
                "return_code": str(payload.get("return_code", "")).strip(),
                "return_status": str(payload.get("return_status", "CREATED")).strip(),
                "refund_status": str(payload.get("refund_status", "PENDING")).strip(),
                "return_reason": str(payload.get("return_reason", "")).strip(),
                "return_tracking_no": str(payload.get("return_tracking_no", "")).strip(),
            }
            if return_request is None:
                return_request = DemoReturnRequest(**values)
                session.add(return_request)
                await session.flush()
            else:
                for key, value in values.items():
                    setattr(return_request, key, value)
            refund_payload = payload.get("refund") or {}
            refund = await session.scalar(
                select(DemoRefund).where(DemoRefund.return_request_id == return_request.id)
            )
            refund_values = {
                "return_request_id": return_request.id,
                "refund_status": str(refund_payload.get("refund_status", values["refund_status"])).strip(),
                "refund_amount": money(refund_payload.get("refund_amount", order.total)),
                "refund_reference": str(refund_payload.get("refund_reference", "")).strip(),
                "refund_reason": str(refund_payload.get("refund_reason", "")).strip(),
                "completed_at": (
                    datetime.fromisoformat(str(refund_payload["completed_at"]))
                    if refund_payload.get("completed_at")
                    else None
                ),
            }
            if refund is None:
                session.add(DemoRefund(**refund_values))
            else:
                for key, value in refund_values.items():
                    setattr(refund, key, value)
            count += 1
        return count

    async def reset_user_scenario(self, session: AsyncSession, user: User) -> dict:
        await self.seed_catalog(session)
        scenario = self.load_demo_json("demo_scenarios.json") or {}
        order_ids = (
            await session.scalars(select(DemoOrder.id).where(DemoOrder.user_id == user.id))
        ).all()
        cart_ids = (
            await session.scalars(select(DemoCart.id).where(DemoCart.user_id == user.id))
        ).all()
        if order_ids:
            await session.execute(
                delete(DemoRefund).where(
                    DemoRefund.return_request_id.in_(
                        select(DemoReturnRequest.id).where(
                            DemoReturnRequest.order_id.in_(order_ids)
                        )
                    )
                )
            )
            await session.execute(
                delete(DemoReturnRequest).where(DemoReturnRequest.order_id.in_(order_ids))
            )
            await session.execute(
                delete(DemoPaymentAttempt).where(
                    (DemoPaymentAttempt.user_id == user.id)
                    | (DemoPaymentAttempt.order_id.in_(order_ids))
                )
            )
            await session.execute(delete(DemoOrder).where(DemoOrder.id.in_(order_ids)))
        else:
            await session.execute(
                delete(DemoPaymentAttempt).where(DemoPaymentAttempt.user_id == user.id)
            )
        if cart_ids:
            await session.execute(delete(DemoCart).where(DemoCart.id.in_(cart_ids)))
        await session.execute(
            delete(DemoProductFavorite).where(DemoProductFavorite.user_id == user.id)
        )
        await session.execute(
            delete(DemoProductReview).where(DemoProductReview.user_id == user.id)
        )
        await session.execute(delete(DemoWallet).where(DemoWallet.user_id == user.id))
        await session.execute(delete(DemoSavedCard).where(DemoSavedCard.user_id == user.id))
        await session.execute(
            delete(DemoUserSecurityProfile).where(DemoUserSecurityProfile.user_id == user.id)
        )
        await session.flush()

        product_rows = (
            await session.scalars(select(DemoProduct).where(DemoProduct.is_active.is_(True)))
        ).all()
        product_by_sku = {product.sku: product for product in product_rows}

        cart = DemoCart(user_id=user.id, status="ACTIVE")
        session.add(cart)
        await session.flush()
        cart_subtotal = Decimal("0")
        cart_categories: set[str] = set()
        for item in (scenario.get("cart") or {}).get("items", []):
            product = product_by_sku.get(str(item.get("sku", "")).strip())
            if product is None:
                continue
            quantity = int(item.get("quantity", 1))
            line_total = money(product.price * quantity)
            session.add(
                DemoCartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.price,
                    line_total=line_total,
                )
            )
            cart_subtotal += line_total
            cart_categories.add(product.category)
        cart.coupon_code = str((scenario.get("cart") or {}).get("coupon_code", "")).strip()
        cart.subtotal = money(cart_subtotal)
        cart.discount_total = Decimal("0")
        cart.total = cart.subtotal
        if cart.coupon_code:
            coupon = await session.scalar(
                select(DemoCoupon).where(DemoCoupon.code == cart.coupon_code)
            )
            if coupon and coupon.is_active and coupon.expires_at and coupon.expires_at >= datetime.now(UTC):
                category_ok = not coupon.allowed_category or coupon.allowed_category in cart_categories
                min_ok = cart.subtotal >= coupon.min_cart_total
                if category_ok and min_ok and coupon.status in {"VALID", "MIN_CART_NOT_MET", "CATEGORY_MISMATCH"}:
                    if coupon.discount_type == "PERCENT":
                        cart.discount_total = money(
                            cart.subtotal * coupon.discount_value / Decimal("100")
                        )
                    else:
                        cart.discount_total = min(coupon.discount_value, cart.subtotal)
                    cart.total = money(max(Decimal("0"), cart.subtotal - cart.discount_total))

        seeded_orders: dict[str, DemoOrder] = {}
        for index, item in enumerate(scenario.get("orders", []), start=1):
            order_items = item.get("items") or []
            if not order_items and item.get("product_sku"):
                order_items = [
                    {
                        "product_sku": item.get("product_sku"),
                        "quantity": item.get("quantity", 1),
                    }
                ]
            resolved_items: list[tuple[object, int]] = []
            for order_item in order_items:
                product = product_by_sku.get(str(order_item.get("product_sku", "")).strip())
                if product is None:
                    continue
                quantity = int(order_item.get("quantity", 1))
                resolved_items.append((product, quantity))
            if not resolved_items:
                continue
            order_no = f"DMO-{user.id}-{str(item.get('order_no_suffix', index)).zfill(3)}"
            subtotal = sum((product.price * quantity for product, quantity in resolved_items), Decimal("0"))
            order = DemoOrder(
                user_id=user.id,
                order_no=order_no,
                order_status=str(item.get("order_status", "PROCESSING")),
                payment_status=str(item.get("payment_status", "SUCCESS")),
                shipping_status=str(item.get("shipping_status", "PREPARING")),
                subtotal=subtotal,
                discount_total=Decimal("0"),
                total=subtotal,
                admin_note=str(item.get("admin_note", "")),
            )
            session.add(order)
            await session.flush()
            for product, quantity in resolved_items:
                line_total = money(product.price * quantity)
                session.add(
                    DemoOrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        product_name=product.name,
                        category=product.category,
                        quantity=quantity,
                        unit_price=product.price,
                        line_total=line_total,
                    )
                )
            session.add(
                DemoShipment(
                    order_id=order.id,
                    carrier=str(item.get("carrier", "Demo Kargo")),
                    tracking_number=str(item.get("tracking_number", f"TRK{user.id}{index:04d}")),
                    status=order.shipping_status,
                    estimated_delivery_at=datetime.now(UTC) + timedelta(days=index),
                    delivered_at=(
                        datetime.now(UTC) if order.shipping_status == "DELIVERED" else None
                    ),
                    delay_reason=str(item.get("delay_reason", "")),
                    admin_note=str(item.get("admin_note", "")),
                )
            )
            session.add(
                DemoPaymentAttempt(
                    user_id=user.id,
                    order_id=order.id,
                    status=order.payment_status,
                    amount=order.total,
                    provider_reference=f"PAY-{order.order_no}",
                )
            )
            seeded_orders[order_no] = order

        await self.seed_demo_return_requests(
            session,
            user,
            seeded_orders,
            scenario.get("returns", []),
        )

        for item in scenario.get("payments", []):
            order = None
            order_ref = item.get("order_ref")
            if order_ref:
                order = seeded_orders.get(str(order_ref))
            if order is None and item.get("order_no_suffix"):
                suffix = str(item.get("order_no_suffix", "")).strip().zfill(3)
                order = next(
                    (entry for key, entry in seeded_orders.items() if key.endswith(f"-{suffix}")),
                    None,
                )
            session.add(
                DemoPaymentAttempt(
                    user_id=user.id,
                    order_id=order.id if order else None,
                    status=str(item.get("status", "CAPTURED_NO_ORDER")),
                    amount=money(item.get("amount", "0")),
                    provider_reference=f"{item.get('provider_reference_prefix', 'PAY')}-{user.id}",
                    failure_reason=str(item.get("failure_reason", "")),
                )
            )

        for item in scenario.get("favorites", []):
            product = product_by_sku.get(str(item.get("sku", "")).strip())
            if product:
                session.add(DemoProductFavorite(user_id=user.id, product_id=product.id))

        for item in scenario.get("reviews", []):
            product = product_by_sku.get(str(item.get("sku", "")).strip())
            if product:
                session.add(
                    DemoProductReview(
                        user_id=user.id,
                        product_id=product.id,
                        rating=item.get("rating"),
                        title=str(item.get("title", "")),
                        body=str(item.get("body", "")),
                        is_verified_purchase=True,
                        is_visible=True,
                    )
                )

        if wallet_payload := scenario.get("wallet"):
            await self.seed_demo_wallet(session, user, wallet_payload)
        if security_payload := scenario.get("security"):
            await self.seed_demo_security(session, user, security_payload)
        await self.seed_demo_saved_cards(session, user, scenario.get("saved_cards", []))
        await session.flush()
        return {
            "products": len(product_rows),
            "coupons": await session.scalar(select(func.count()).select_from(DemoCoupon)) or 0,
            "orders": len(seeded_orders),
        }

    async def prepare_demo_scenario(
        self, session: AsyncSession, user: User, scenario_key: str
    ) -> dict:
        await self.seed_catalog(session)
        await self.clear_demo_scenario(session, user, scenario_key)
        product_rows = (
            await session.scalars(select(DemoProduct).where(DemoProduct.is_active.is_(True)))
        ).all()
        product_by_sku = {product.sku: product for product in product_rows}

        if scenario_key == "payment-captured-no-order":
            session.add(
                DemoPaymentAttempt(
                    user_id=user.id,
                    order_id=None,
                    status="CAPTURED_NO_ORDER",
                    amount=money("899.90"),
                    provider_reference=f"{SCENARIO_MARKERS[scenario_key]}-{user.id}",
                    failure_reason="Ödeme başarılı döndü ancak sipariş kaydı oluşmadı.",
                )
            )
        elif scenario_key == "order-not-shipped":
            await self._create_scenario_order(
                session,
                user,
                product_by_sku,
                scenario_key,
                "BAGS-BACKPACK-001",
                order_status="PROCESSING",
                payment_status="SUCCESS",
                shipping_status="PREPARING",
                admin_note="Hazırlanan sipariş henüz kargoya verilmedi.",
            )
        elif scenario_key == "delivered-not-received":
            await self._create_scenario_order(
                session,
                user,
                product_by_sku,
                scenario_key,
                "ELECTRONICS-HEADPHONE-001",
                order_status="DELIVERED",
                payment_status="SUCCESS",
                shipping_status="DELIVERED",
                admin_note="Teslim edildi görünüyor ancak müşteri ürünü almadığını belirtti.",
                return_payload={
                    "return_request": "CREATED",
                    "return_code": f"RET-DNR-{user.id}",
                    "return_status": "UNDER_REVIEW",
                    "refund_status": "PENDING",
                    "return_reason": "Teslim edildi görünüyor ama kullanıcı teslim almadığını belirtti.",
                    "return_tracking_no": f"RR-DNR-{user.id}",
                },
            )
        elif scenario_key == "returnable-product":
            await self._create_scenario_order(
                session,
                user,
                product_by_sku,
                scenario_key,
                "HOME-CAY-BARDAGI-6",
                order_status="DELIVERED",
                payment_status="SUCCESS",
                shipping_status="DELIVERED",
                admin_note="İade edilebilir ürün teslim edildi.",
            )
        elif scenario_key == "non-returnable-product":
            await self._create_scenario_order(
                session,
                user,
                product_by_sku,
                scenario_key,
                "MARKET-CAY-YESIL-250",
                order_status="DELIVERED",
                payment_status="SUCCESS",
                shipping_status="DELIVERED",
                admin_note="İade edilemeyen ürün teslim edildi.",
            )
        elif scenario_key == EXPIRED_COUPON_SCENARIO:
            cart = await self._active_scenario_cart(session, user)
            cart.coupon_code = "ESKI50"
            cart.discount_total = Decimal("0")
            cart.total = cart.subtotal
        else:
            raise ValueError("Bilinmeyen demo senaryosu.")
        await session.flush()
        return {"key": scenario_key, "prepared": True, "status": "Senaryo hazırlandı."}

    async def clear_demo_scenario(
        self, session: AsyncSession, user: User, scenario_key: str
    ) -> dict:
        if scenario_key in SCENARIO_MARKERS:
            marker = SCENARIO_MARKERS[scenario_key]
            order_ids = (
                await session.scalars(
                    select(DemoOrder.id).where(
                        DemoOrder.user_id == user.id,
                        DemoOrder.admin_note.like(f"{marker}%"),
                    )
                )
            ).all()
            if order_ids:
                await session.execute(
                    delete(DemoRefund).where(
                        DemoRefund.return_request_id.in_(
                            select(DemoReturnRequest.id).where(
                                DemoReturnRequest.order_id.in_(order_ids)
                            )
                        )
                    )
                )
                await session.execute(
                    delete(DemoReturnRequest).where(
                        DemoReturnRequest.order_id.in_(order_ids)
                    )
                )
                await session.execute(
                    delete(DemoPaymentAttempt).where(
                        DemoPaymentAttempt.order_id.in_(order_ids)
                    )
                )
                await session.execute(delete(DemoOrder).where(DemoOrder.id.in_(order_ids)))
            await session.execute(
                delete(DemoPaymentAttempt).where(
                    DemoPaymentAttempt.user_id == user.id,
                    DemoPaymentAttempt.provider_reference.like(f"{marker}%"),
                )
            )
        elif scenario_key == EXPIRED_COUPON_SCENARIO:
            carts = (
                await session.scalars(
                    select(DemoCart).where(
                        DemoCart.user_id == user.id,
                        DemoCart.status == "ACTIVE",
                        DemoCart.coupon_code == "ESKI50",
                    )
                )
            ).all()
            for cart in carts:
                cart.coupon_code = ""
                cart.discount_total = Decimal("0")
                cart.total = cart.subtotal
        else:
            raise ValueError("Bilinmeyen demo senaryosu.")
        await session.flush()
        return {"key": scenario_key, "prepared": False, "status": "Senaryo temizlendi."}

    async def demo_scenario_statuses(
        self, session: AsyncSession, user: User
    ) -> list[dict]:
        statuses: list[dict] = []
        for key, marker in SCENARIO_MARKERS.items():
            order_exists = await session.scalar(
                select(func.count()).select_from(DemoOrder).where(
                    DemoOrder.user_id == user.id,
                    DemoOrder.admin_note.like(f"{marker}%"),
                )
            )
            payment_exists = await session.scalar(
                select(func.count()).select_from(DemoPaymentAttempt).where(
                    DemoPaymentAttempt.user_id == user.id,
                    DemoPaymentAttempt.provider_reference.like(f"{marker}%"),
                )
            )
            prepared = bool((order_exists or 0) + (payment_exists or 0))
            statuses.append(
                {
                    "key": key,
                    "prepared": prepared,
                    "status": "Hazırlandı" if prepared else "Hazır değil",
                }
            )
        expired_coupon = await session.scalar(
            select(func.count()).select_from(DemoCart).where(
                DemoCart.user_id == user.id,
                DemoCart.status == "ACTIVE",
                DemoCart.coupon_code == "ESKI50",
            )
        )
        prepared = bool(expired_coupon or 0)
        statuses.append(
            {
                "key": EXPIRED_COUPON_SCENARIO,
                "prepared": prepared,
                "status": "Hazırlandı" if prepared else "Hazır değil",
            }
        )
        return statuses

    async def _active_scenario_cart(self, session: AsyncSession, user: User) -> DemoCart:
        cart = await session.scalar(
            select(DemoCart).where(DemoCart.user_id == user.id, DemoCart.status == "ACTIVE")
        )
        if cart is None:
            cart = DemoCart(user_id=user.id, status="ACTIVE")
            session.add(cart)
            await session.flush()
        return cart

    async def _create_scenario_order(
        self,
        session: AsyncSession,
        user: User,
        product_by_sku: dict[str, DemoProduct],
        scenario_key: str,
        sku: str,
        *,
        order_status: str,
        payment_status: str,
        shipping_status: str,
        admin_note: str,
        return_payload: dict | None = None,
    ) -> DemoOrder | None:
        product = product_by_sku.get(sku)
        if product is None:
            return None
        marker = SCENARIO_MARKERS[scenario_key]
        order_no = f"DSC-{user.id}-{scenario_key.upper().replace('-', '')[:12]}"
        order = DemoOrder(
            user_id=user.id,
            order_no=order_no,
            order_status=order_status,
            payment_status=payment_status,
            shipping_status=shipping_status,
            subtotal=product.price,
            discount_total=Decimal("0"),
            total=product.price,
            admin_note=f"{marker} · {admin_note}",
        )
        session.add(order)
        await session.flush()
        session.add(
            DemoOrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                category=product.category,
                quantity=1,
                unit_price=product.price,
                line_total=product.price,
            )
        )
        session.add(
            DemoShipment(
                order_id=order.id,
                carrier="Demo Kargo",
                tracking_number=f"TRK-{scenario_key[:4].upper()}-{user.id}",
                status=shipping_status,
                estimated_delivery_at=datetime.now(UTC) + timedelta(days=1),
                delivered_at=datetime.now(UTC) if shipping_status == "DELIVERED" else None,
                delay_reason=admin_note if shipping_status != "DELIVERED" else "",
                admin_note=admin_note,
            )
        )
        session.add(
            DemoPaymentAttempt(
                user_id=user.id,
                order_id=order.id,
                status=payment_status,
                amount=order.total,
                provider_reference=f"{marker}-{user.id}",
            )
        )
        if return_payload:
            return_request = DemoReturnRequest(
                order_id=order.id,
                user_id=user.id,
                return_request=str(return_payload["return_request"]),
                return_code=str(return_payload["return_code"]),
                return_status=str(return_payload["return_status"]),
                refund_status=str(return_payload["refund_status"]),
                return_reason=str(return_payload["return_reason"]),
                return_tracking_no=str(return_payload["return_tracking_no"]),
            )
            session.add(return_request)
            await session.flush()
            session.add(
                DemoRefund(
                    return_request_id=return_request.id,
                    refund_status=return_request.refund_status,
                    refund_amount=order.total,
                    refund_reference=f"RF-{scenario_key[:4].upper()}-{user.id}",
                    refund_reason=return_request.return_reason,
                )
            )
        return order
