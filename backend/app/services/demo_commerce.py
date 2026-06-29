from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    DemoCart,
    DemoCartItem,
    DemoCoupon,
    DemoOrder,
    DemoOrderItem,
    DemoPaymentAttempt,
    DemoProduct,
    DemoShipment,
    DemoReturnRequest,
    User,
)
from .demo_seed import DemoSeedService


STATUS_LABELS = {
    "PREPARING": "Hazırlanıyor",
    "SHIPPED": "Kargoya verildi",
    "IN_TRANSIT": "Yolda",
    "DELAYED": "Gecikti",
    "LOST": "Kayboldu",
    "DELIVERED": "Teslim edildi",
    "SUCCESS": "Ödeme başarılı",
    "FAILED": "Ödeme başarısız",
    "CAPTURED_NO_ORDER": "Ödeme alındı ama sipariş oluşmadı",
    "REFUND_PENDING": "İade bekliyor",
    "CREATED": "Oluşturuldu",
    "PROCESSING": "İşleniyor",
    "CANCELLED": "İptal edildi",
}


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


class DemoCommerceService:
    async def ensure_seed_data(self, session: AsyncSession) -> None:
        await DemoSeedService().seed_catalog(session)

    async def active_cart(self, session: AsyncSession, user: User) -> DemoCart:
        await self.ensure_seed_data(session)
        cart = await session.scalar(
            select(DemoCart)
            .options(selectinload(DemoCart.items).selectinload(DemoCartItem.product))
            .where(DemoCart.user_id == user.id, DemoCart.status == "ACTIVE")
            .order_by(DemoCart.id.desc())
        )
        if cart:
            return cart
        cart = DemoCart(user_id=user.id, status="ACTIVE")
        session.add(cart)
        await session.flush()
        await session.refresh(cart, ["items"])
        return cart

    async def recalculate_cart(self, session: AsyncSession, cart: DemoCart) -> str:
        await session.refresh(cart, ["items"])
        subtotal = sum((item.line_total for item in cart.items), Decimal("0"))
        discount = Decimal("0")
        message = ""
        coupon = None
        if cart.coupon_code:
            coupon = await session.scalar(
                select(DemoCoupon).where(DemoCoupon.code == cart.coupon_code)
            )
        if coupon:
            valid, message = self.validate_coupon(coupon, cart.items, subtotal)
            if valid:
                if coupon.discount_type == "PERCENT":
                    discount = money(subtotal * coupon.discount_value / Decimal("100"))
                else:
                    discount = min(coupon.discount_value, subtotal)
            else:
                discount = Decimal("0")
        cart.subtotal = money(subtotal)
        cart.discount_total = money(discount)
        cart.total = money(max(Decimal("0"), subtotal - discount))
        return message

    def validate_coupon(
        self, coupon: DemoCoupon, items: list[DemoCartItem], subtotal: Decimal
    ) -> tuple[bool, str]:
        now = datetime.now(UTC)
        if not coupon.is_active or coupon.status == "DISABLED":
            return False, "Kupon aktif değil."
        if coupon.status == "EXPIRED" or (
            coupon.expires_at and coupon.expires_at < now
        ):
            return False, "Kuponun süresi dolmuş."
        if subtotal < coupon.min_cart_total:
            return False, "Minimum sepet tutarı yetersiz."
        if coupon.allowed_category:
            categories = {item.product.category for item in items if item.product}
            if coupon.allowed_category not in categories:
                return False, "Kupon sepetteki ürün kategorileri için uygun değil."
        if coupon.status not in {"VALID", "MIN_CART_NOT_MET", "CATEGORY_MISMATCH"}:
            return False, "Kupon bu işlem için uygun değil."
        return True, "Kupon uygulandı."

    async def add_cart_item(
        self, session: AsyncSession, user: User, product_id: int, quantity: int
    ) -> DemoCart:
        cart = await self.active_cart(session, user)
        product = await session.get(DemoProduct, product_id)
        if not product or not product.is_active:
            raise HTTPException(404, "Ürün bulunamadı.")
        if product.stock < quantity:
            raise HTTPException(400, "Ürün stoğu yetersiz.")
        existing = next(
            (item for item in cart.items if item.product_id == product.id), None
        )
        if existing:
            existing.quantity += quantity
            existing.line_total = money(existing.unit_price * existing.quantity)
        else:
            session.add(
                DemoCartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.price,
                    line_total=money(product.price * quantity),
                )
            )
        await session.flush()
        await self.recalculate_cart(session, cart)
        return await self.active_cart(session, user)

    async def update_cart_item(
        self, session: AsyncSession, user: User, item_id: int, quantity: int
    ) -> DemoCart:
        cart = await self.active_cart(session, user)
        item = next((entry for entry in cart.items if entry.id == item_id), None)
        if not item:
            raise HTTPException(404, "Sepet ürünü bulunamadı.")
        item.quantity = quantity
        item.line_total = money(item.unit_price * quantity)
        await self.recalculate_cart(session, cart)
        return await self.active_cart(session, user)

    async def remove_cart_item(
        self, session: AsyncSession, user: User, item_id: int
    ) -> DemoCart:
        cart = await self.active_cart(session, user)
        item = next((entry for entry in cart.items if entry.id == item_id), None)
        if item:
            await session.delete(item)
            await session.flush()
        await self.recalculate_cart(session, cart)
        return await self.active_cart(session, user)

    async def apply_coupon(
        self, session: AsyncSession, user: User, code: str
    ) -> tuple[DemoCart, str]:
        cart = await self.active_cart(session, user)
        coupon = await session.scalar(
            select(DemoCoupon).where(DemoCoupon.code == code.strip().upper())
        )
        if not coupon:
            cart.coupon_code = ""
            await self.recalculate_cart(session, cart)
            return await self.active_cart(session, user), "Kupon bulunamadı."
        cart.coupon_code = coupon.code
        message = await self.recalculate_cart(session, cart)
        return await self.active_cart(session, user), message

    async def checkout(self, session: AsyncSession, user: User) -> DemoOrder:
        cart = await self.active_cart(session, user)
        if not cart.items:
            raise HTTPException(400, "Sepet boş.")
        await self.recalculate_cart(session, cart)
        order_no = f"DMO-{user.id}-{int(datetime.now(UTC).timestamp())}"
        order = DemoOrder(
            user_id=user.id,
            order_no=order_no,
            order_status="PROCESSING",
            payment_status="SUCCESS",
            shipping_status="PREPARING",
            coupon_code=cart.coupon_code,
            subtotal=cart.subtotal,
            discount_total=cart.discount_total,
            total=cart.total,
        )
        session.add(order)
        await session.flush()
        for item in cart.items:
            session.add(
                DemoOrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product.name if item.product else "Ürün",
                    category=item.product.category if item.product else "",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
            )
        session.add(
            DemoShipment(
                order_id=order.id,
                status="PREPARING",
                carrier="Demo Kargo",
                estimated_delivery_at=datetime.now(UTC) + timedelta(days=3),
            )
        )
        session.add(
            DemoPaymentAttempt(
                user_id=user.id,
                order_id=order.id,
                status="SUCCESS",
                amount=order.total,
                provider_reference=f"PAY-{order_no}",
            )
        )
        cart.status = "CHECKED_OUT"
        await session.flush()
        return await self.get_order(session, user, order.id)

    async def get_order(self, session: AsyncSession, user: User, order_id: int) -> DemoOrder:
        order = await session.scalar(
            select(DemoOrder)
            .options(
                selectinload(DemoOrder.items),
                selectinload(DemoOrder.shipment),
                selectinload(DemoOrder.return_request)
                .selectinload(DemoReturnRequest.refund),
                selectinload(DemoOrder.return_request)
                .selectinload(DemoReturnRequest.order),
            )
            .where(DemoOrder.id == order_id, DemoOrder.user_id == user.id)
        )
        if not order:
            raise HTTPException(404, "Sipariş bulunamadı.")
        return order

    async def reset_user_demo(self, session: AsyncSession, user: User) -> dict:
        return await DemoSeedService().reset_user_scenario(session, user)


class CustomerContextService:
    CANCELABLE_ORDER_STATUSES = {"CREATED", "PROCESSING", "PREPARING"}
    SHIPPED_STATUSES = {"SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"}

    def _detect_intent(self, category: str, canonical_query: str) -> str:
        normalized = re.sub(r"\s+", " ", canonical_query.casefold()).strip()
        if category == "SIPARIS" and "iptal" in normalized:
            if any(term in normalized for term in ("kargo", "kargoya", "gönderildi", "yola çıktı")):
                return "shipped_order_cancel"
            return "order_cancel"
        if category == "KARGO_TESLIMAT":
            if (
                "teslim edildi" in normalized
                and any(term in normalized for term in ("ulaşmadı", "gelmedi", "almadım", "bana ulaşmadı"))
            ):
                return "delivered_not_received"
            if "iptal" in normalized:
                return "shipped_order_cancel"
            return "shipping_status"
        if category == "IADE":
            if "kod" in normalized:
                return "return_code"
            return "return_request"
        if category == "KAMPANYA_PUAN":
            if any(term in normalized for term in ("kupon", "indirim", "çalışmıyor", "calismiyor")):
                return "coupon_issue"
        if category == "ODEME":
            if any(term in normalized for term in ("para çekildi", "para cekildi", "kartımdan", "siparişim oluşmadı", "siparisim olusmadi")):
                return "payment_without_order"
        return ""

    def _order_line(self, order: DemoOrder, decision: str = "") -> str:
        shipment = order.shipment
        item_names = ", ".join(item.product_name for item in order.items[:3])
        parts = [
            f"ürünler={item_names}",
            f"sipariş durumu={STATUS_LABELS.get(order.order_status, order.order_status)}",
            f"ödeme={STATUS_LABELS.get(order.payment_status, order.payment_status)}",
            f"kargo={STATUS_LABELS.get(order.shipping_status, order.shipping_status)}",
        ]
        if shipment and shipment.tracking_number:
            parts.append(f"takip no={shipment.tracking_number}")
        note = (order.admin_note or (shipment.admin_note if shipment else "")).strip()
        if note:
            parts.append(f"not={note.rstrip('.')}")
        if decision:
            parts.append(f"karar={decision}")
        return f"Sipariş {order.order_no}: " + "; ".join(parts) + "."

    def _cancel_decision(self, order: DemoOrder) -> str:
        if (
            order.order_status in self.CANCELABLE_ORDER_STATUSES
            and order.shipping_status not in self.SHIPPED_STATUSES
        ):
            return "Bu sipariş iptale uygun olabilir; iptal talebi oluşturulabilir."
        return "Bu sipariş kargoya verildiği veya tamamlandığı için iptal edilemez; teslim sonrası iade süreci önerilir."

    def _selected_orders_for_intent(
        self, orders: list[DemoOrder], category: str, intent: str
    ) -> list[DemoOrder]:
        if intent == "delivered_not_received":
            delivered = [order for order in orders if order.shipping_status == "DELIVERED"]
            return delivered or orders
        if intent == "shipped_order_cancel":
            shipped = [order for order in orders if order.shipping_status in self.SHIPPED_STATUSES]
            return shipped or orders
        if intent == "order_cancel":
            cancel_related = [
                order
                for order in orders
                if order.order_status in self.CANCELABLE_ORDER_STATUSES
                or order.shipping_status in self.SHIPPED_STATUSES
            ]
            return cancel_related or orders
        if intent in {"return_code", "return_request"}:
            return_ready = [
                order
                for order in orders
                if order.shipping_status == "DELIVERED"
                or order.payment_status == "REFUND_PENDING"
            ]
            return return_ready or orders
        if category == "KARGO_TESLIMAT":
            active_shipping_orders = [
                order for order in orders if order.shipping_status not in {"DELIVERED", "LOST"}
            ]
            return active_shipping_orders or orders
        return orders

    async def build(
        self,
        session: AsyncSession,
        user: User,
        category: str,
        canonical_query: str,
        selected_order_no: str | None = None,
        selected_order_id: int | None = None,
    ) -> dict:
        commerce = DemoCommerceService()
        await commerce.ensure_seed_data(session)
        intent = self._detect_intent(category, canonical_query)
        context: dict = {
            "category": category,
            "intent": intent,
            "context_type": "intent" if intent else "clarification_needed",
            "items": [],
            "text": "",
            "decision_hints": [],
            "selected_counts": {"orders": 0, "payments": 0, "cart": 0},
        }
        if category == "HESAP_GUVENLIK":
            return context
        order_query = (
            select(DemoOrder)
            .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
            .where(DemoOrder.user_id == user.id)
            .order_by(DemoOrder.updated_at.desc())
        )
        if selected_order_id is not None:
            order_query = order_query.where(DemoOrder.id == selected_order_id)
        elif selected_order_no:
            order_query = order_query.where(DemoOrder.order_no == selected_order_no)
        else:
            order_query = order_query.limit(3)
        orders = (await session.scalars(order_query)).all()
        cart = await session.scalar(
            select(DemoCart)
            .options(selectinload(DemoCart.items).selectinload(DemoCartItem.product))
            .where(DemoCart.user_id == user.id, DemoCart.status == "ACTIVE")
            .order_by(DemoCart.id.desc())
        )
        payment_query = (
            select(DemoPaymentAttempt)
            .where(DemoPaymentAttempt.user_id == user.id)
            .order_by(DemoPaymentAttempt.created_at.desc())
            .limit(3)
        )
        if intent == "payment_without_order":
            payment_query = (
                select(DemoPaymentAttempt)
                .where(
                    DemoPaymentAttempt.user_id == user.id,
                    DemoPaymentAttempt.order_id.is_(None),
                    DemoPaymentAttempt.status.in_({"SUCCESS", "CAPTURED_NO_ORDER"}),
                )
                .order_by(DemoPaymentAttempt.created_at.desc())
                .limit(3)
            )
        payments = (await session.scalars(payment_query)).all()

        lines = []
        decision_hints = []
        if category in {"SIPARIS", "KARGO_TESLIMAT", "IADE", "ODEME"}:
            relevant_orders = (
                []
                if intent == "payment_without_order"
                else self._selected_orders_for_intent(orders, category, intent)
            )
            for order in relevant_orders:
                decision = ""
                if intent in {"order_cancel", "shipped_order_cancel"}:
                    decision = self._cancel_decision(order)
                    decision_hints.append(f"{order.order_no}: {decision}")
                elif intent == "delivered_not_received":
                    decision = "Teslim edildi göründüğü halde ulaşmadıysa destek kaydı açılması önerilir."
                    decision_hints.append(f"{order.order_no}: {decision}")
                elif intent == "return_code":
                    decision = "İade kodu için teslim edilmiş veya iade sürecine uygun sipariş üzerinden iade talebi oluşturulmalıdır."
                    decision_hints.append(f"{order.order_no}: {decision}")
                lines.append(self._order_line(order, decision))
            context["selected_counts"]["orders"] = len(relevant_orders)
        if category == "ODEME":
            relevant_payments = payments
            for payment in relevant_payments:
                linked = "siparişe bağlı" if payment.order_id else "siparişe bağlı değil"
                if intent == "payment_without_order" and not payment.order_id and payment.status in {"SUCCESS", "CAPTURED_NO_ORDER"}:
                    decision_hints.append(
                        "Siparişe bağlı olmayan başarılı/çekilmiş ödeme var; HIGH öncelikli destek kaydı önerilir."
                    )
                lines.append(
                    f"Ödeme kaydı {payment.provider_reference}: "
                    f"durum={STATUS_LABELS.get(payment.status, payment.status)}; "
                    f"tutar={payment.amount}; bağlantı={linked}; açıklama={payment.failure_reason}."
                )
            if intent == "payment_without_order" and not decision_hints:
                decision_hints.append("Mevcut ödeme kayıtları siparişlerle eşleşiyor görünüyor.")
            context["selected_counts"]["payments"] = len(relevant_payments)
        if category == "KAMPANYA_PUAN" and cart:
            coupon_message = await commerce.recalculate_cart(session, cart)
            product_names = ", ".join(
                item.product.name for item in cart.items[:3] if item.product
            )
            if not cart.items:
                decision_hints.append("Aktif sepet boş olduğu için kupon uygulanamaz.")
            elif not cart.coupon_code:
                decision_hints.append("Aktif sepette girilmiş kupon kodu görünmüyor.")
            else:
                decision_hints.append(coupon_message or "Kupon durumu doğrulanamadı.")
            lines.append(
                f"Aktif sepet: ürünler={product_names}; ara toplam={cart.subtotal}; "
                f"kupon={cart.coupon_code or 'yok'}; indirim={cart.discount_total}; "
                f"toplam={cart.total}; kupon durumu={coupon_message or 'kupon yok'}."
            )
            context["selected_counts"]["cart"] = 1
        context["decision_hints"] = decision_hints
        context["items"] = lines
        if intent:
            hint_text = "\n".join(f"Karar notu: {hint}" for hint in decision_hints[:5])
            context["text"] = "\n".join(part for part in ["\n".join(lines[:5]), hint_text] if part)
        else:
            context["text"] = ""
        return context
