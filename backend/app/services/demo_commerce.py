from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
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
    User,
)


PRODUCT_SEED = [
    ("Kablosuz Kulaklık", "ELEKTRONIK", Decimal("899.90"), 25),
    ("Akıllı Saat", "ELEKTRONIK", Decimal("1499.90"), 15),
    ("Spor Ayakkabı", "MODA", Decimal("1199.90"), 20),
    ("Sırt Çantası", "MODA", Decimal("599.90"), 30),
    ("Filtre Kahve Makinesi", "EV_YASAM", Decimal("2199.90"), 8),
    ("Ofis Sandalyesi", "EV_YASAM", Decimal("3499.90"), 6),
]

COUPON_SEED = [
    ("DEMO10", "VALID", "PERCENT", Decimal("10"), Decimal("0"), None, True),
    ("MIN500", "MIN_CART_NOT_MET", "AMOUNT", Decimal("100"), Decimal("500"), None, True),
    ("MODA20", "CATEGORY_MISMATCH", "PERCENT", Decimal("20"), Decimal("0"), "MODA", True),
    ("ESKI50", "EXPIRED", "AMOUNT", Decimal("50"), Decimal("0"), None, True),
]

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
        existing_products = await session.scalar(
            select(func.count()).select_from(DemoProduct)
        )
        if not existing_products:
            session.add_all(
                [
                    DemoProduct(
                        name=name,
                        category=category,
                        price=price,
                        stock=stock,
                        is_active=True,
                    )
                    for name, category, price, stock in PRODUCT_SEED
                ]
            )
        existing_coupons = await session.scalar(
            select(func.count()).select_from(DemoCoupon)
        )
        if not existing_coupons:
            now = datetime.now(UTC)
            session.add_all(
                [
                    DemoCoupon(
                        code=code,
                        status=status,
                        discount_type=discount_type,
                        discount_value=value,
                        min_cart_total=min_total,
                        allowed_category=category or "",
                        expires_at=now - timedelta(days=1)
                        if status == "EXPIRED"
                        else now + timedelta(days=30),
                        is_active=is_active,
                    )
                    for code, status, discount_type, value, min_total, category, is_active in COUPON_SEED
                ]
            )
        await session.flush()

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
            )
            .where(DemoOrder.id == order_id, DemoOrder.user_id == user.id)
        )
        if not order:
            raise HTTPException(404, "Sipariş bulunamadı.")
        return order

    async def reset_user_demo(self, session: AsyncSession, user: User) -> dict:
        await self.ensure_seed_data(session)
        order_ids = (
            await session.scalars(select(DemoOrder.id).where(DemoOrder.user_id == user.id))
        ).all()
        cart_ids = (
            await session.scalars(select(DemoCart.id).where(DemoCart.user_id == user.id))
        ).all()
        if order_ids:
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
        products = (
            await session.scalars(select(DemoProduct).where(DemoProduct.is_active.is_(True)))
        ).all()
        product_by_category = defaultdict(list)
        for product in products:
            product_by_category[product.category].append(product)
        cart = DemoCart(user_id=user.id, status="ACTIVE")
        session.add(cart)
        await session.flush()
        for product in products[:2]:
            session.add(
                DemoCartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=product.price,
                    line_total=product.price,
                )
            )
        await self.recalculate_cart(session, cart)

        seeded_orders = []
        scenarios = [
            ("PROCESSING", "SUCCESS", "DELAYED", "Kargo operasyon yoğunluğu"),
            ("SHIPPED", "SUCCESS", "IN_TRANSIT", ""),
            ("DELIVERED", "REFUND_PENDING", "DELIVERED", "İade kontrolü bekleniyor"),
        ]
        for index, (order_status, payment_status, shipping_status, note) in enumerate(
            scenarios, start=1
        ):
            product = products[(index + 1) % len(products)]
            order = DemoOrder(
                user_id=user.id,
                order_no=f"DMO-{user.id}-{index:03d}",
                order_status=order_status,
                payment_status=payment_status,
                shipping_status=shipping_status,
                subtotal=product.price,
                discount_total=Decimal("0"),
                total=product.price,
                admin_note=note,
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
                    tracking_number=f"TRK{user.id}{index:04d}",
                    status=shipping_status,
                    estimated_delivery_at=datetime.now(UTC) + timedelta(days=index),
                    delay_reason=note if shipping_status == "DELAYED" else "",
                    delivered_at=datetime.now(UTC) if shipping_status == "DELIVERED" else None,
                    admin_note=note,
                )
            )
            session.add(
                DemoPaymentAttempt(
                    user_id=user.id,
                    order_id=order.id,
                    status=payment_status,
                    amount=order.total,
                    provider_reference=f"PAY-{order.order_no}",
                )
            )
            seeded_orders.append(order)
        session.add(
            DemoPaymentAttempt(
                user_id=user.id,
                order_id=None,
                status="CAPTURED_NO_ORDER",
                amount=Decimal("899.90"),
                provider_reference=f"PAY-NOORDER-{user.id}",
                failure_reason="Ödeme başarılı döndü ancak sipariş kaydı oluşmadı.",
            )
        )
        await session.flush()
        return {"products": len(products), "coupons": 4, "orders": len(seeded_orders)}


class CustomerContextService:
    async def build(
        self,
        session: AsyncSession,
        user: User,
        category: str,
        canonical_query: str,
        selected_order_no: str | None = None,
    ) -> dict:
        del canonical_query
        commerce = DemoCommerceService()
        await commerce.ensure_seed_data(session)
        context: dict = {"category": category, "items": [], "text": ""}
        if category == "HESAP_GUVENLIK":
            return context
        order_query = (
            select(DemoOrder)
            .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
            .where(DemoOrder.user_id == user.id)
            .order_by(DemoOrder.updated_at.desc())
        )
        if selected_order_no:
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
        payments = (
            await session.scalars(
                select(DemoPaymentAttempt)
                .where(DemoPaymentAttempt.user_id == user.id)
                .order_by(DemoPaymentAttempt.created_at.desc())
                .limit(3)
            )
        ).all()

        lines = []
        if category in {"SIPARIS", "KARGO_TESLIMAT", "IADE", "ODEME"}:
            relevant_orders = orders
            if category == "KARGO_TESLIMAT":
                active_shipping_orders = [
                    order
                    for order in orders
                    if order.shipping_status not in {"DELIVERED", "LOST"}
                ]
                relevant_orders = active_shipping_orders or orders
            for order in relevant_orders:
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
                lines.append(f"Sipariş {order.order_no}: " + "; ".join(parts) + ".")
        if category == "ODEME":
            for payment in payments:
                lines.append(
                    f"Ödeme kaydı {payment.provider_reference}: "
                    f"durum={STATUS_LABELS.get(payment.status, payment.status)}; "
                    f"tutar={payment.amount}; açıklama={payment.failure_reason}."
                )
        if category == "KAMPANYA_PUAN" and cart:
            coupon_message = await commerce.recalculate_cart(session, cart)
            product_names = ", ".join(
                item.product.name for item in cart.items[:3] if item.product
            )
            lines.append(
                f"Aktif sepet: ürünler={product_names}; ara toplam={cart.subtotal}; "
                f"kupon={cart.coupon_code or 'yok'}; indirim={cart.discount_total}; "
                f"toplam={cart.total}; kupon durumu={coupon_message or 'kupon yok'}."
            )
        context["items"] = lines
        context["text"] = "\n".join(lines[:5])
        return context
