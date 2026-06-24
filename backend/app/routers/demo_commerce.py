from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..models import (
    DemoCart,
    DemoCartItem,
    DemoCoupon,
    DemoOrder,
    DemoPaymentAttempt,
    DemoProduct,
    DemoShipment,
    User,
)
from ..schemas.demo_commerce import (
    AdminCouponCreate,
    AdminCouponUpdate,
    AdminOrderUpdate,
    AdminPaymentAttemptCreate,
    AdminShipmentUpdate,
    CartItemCreate,
    CartItemUpdate,
    CouponApplyRequest,
    DemoCartItemResponse,
    DemoCartResponse,
    DemoCouponResponse,
    DemoOrderItemResponse,
    DemoOrderResponse,
    DemoProductResponse,
    DemoResetResponse,
    DemoShipmentResponse,
)
from ..services.auth import get_current_user, require_admin
from ..services.demo_commerce import DemoCommerceService


router = APIRouter(prefix="/api", tags=["demo-commerce"])


def product_response(product: DemoProduct) -> DemoProductResponse:
    return DemoProductResponse(
        id=product.id,
        name=product.name,
        category=product.category,
        price=product.price,
        stock=product.stock,
        is_active=product.is_active,
        image_url=product.image_url,
    )


def cart_response(cart: DemoCart, coupon_message: str = "") -> DemoCartResponse:
    return DemoCartResponse(
        id=cart.id,
        status=cart.status,
        coupon_code=cart.coupon_code,
        subtotal=cart.subtotal,
        discount_total=cart.discount_total,
        total=cart.total,
        coupon_message=coupon_message,
        items=[
            DemoCartItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else "Ürün",
                category=item.product.category if item.product else "",
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in cart.items
        ],
    )


def shipment_response(shipment: DemoShipment | None) -> DemoShipmentResponse | None:
    if shipment is None:
        return None
    return DemoShipmentResponse(
        carrier=shipment.carrier,
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        estimated_delivery_at=shipment.estimated_delivery_at,
        delivered_at=shipment.delivered_at,
        delay_reason=shipment.delay_reason,
        admin_note=shipment.admin_note,
    )


def order_response(order: DemoOrder) -> DemoOrderResponse:
    return DemoOrderResponse(
        id=order.id,
        order_no=order.order_no,
        order_status=order.order_status,
        payment_status=order.payment_status,
        shipping_status=order.shipping_status,
        coupon_code=order.coupon_code,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        total=order.total,
        admin_note=order.admin_note,
        created_at=order.created_at,
        updated_at=order.updated_at,
        shipment=shipment_response(order.shipment),
        items=[
            DemoOrderItemResponse(
                product_name=item.product_name,
                category=item.category,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in order.items
        ],
    )


def coupon_response(coupon: DemoCoupon) -> DemoCouponResponse:
    return DemoCouponResponse(
        id=coupon.id,
        code=coupon.code,
        status=coupon.status,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        min_cart_total=coupon.min_cart_total,
        allowed_category=coupon.allowed_category,
        expires_at=coupon.expires_at,
        is_active=coupon.is_active,
    )


@router.get("/demo/products", response_model=list[DemoProductResponse])
async def products(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DemoProductResponse]:
    service = DemoCommerceService()
    await service.ensure_seed_data(session)
    items = (
        await session.scalars(
            select(DemoProduct)
            .where(DemoProduct.is_active.is_(True))
            .order_by(DemoProduct.category, DemoProduct.name)
        )
    ).all()
    return [product_response(item) for item in items]


@router.get("/demo/cart", response_model=DemoCartResponse)
async def cart(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoCartResponse:
    service = DemoCommerceService()
    item = await service.active_cart(session, user)
    message = await service.recalculate_cart(session, item)
    await session.commit()
    return cart_response(item, message)


@router.post("/demo/cart/items", response_model=DemoCartResponse)
async def add_cart_item(
    payload: CartItemCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoCartResponse:
    item = await DemoCommerceService().add_cart_item(
        session, user, payload.product_id, payload.quantity
    )
    await session.commit()
    return cart_response(item)


@router.patch("/demo/cart/items/{item_id}", response_model=DemoCartResponse)
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoCartResponse:
    item = await DemoCommerceService().update_cart_item(
        session, user, item_id, payload.quantity
    )
    await session.commit()
    return cart_response(item)


@router.delete("/demo/cart/items/{item_id}", response_model=DemoCartResponse)
async def delete_cart_item(
    item_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoCartResponse:
    item = await DemoCommerceService().remove_cart_item(session, user, item_id)
    await session.commit()
    return cart_response(item)


@router.post("/demo/cart/apply-coupon", response_model=DemoCartResponse)
async def apply_coupon(
    payload: CouponApplyRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoCartResponse:
    item, message = await DemoCommerceService().apply_coupon(
        session, user, payload.code
    )
    await session.commit()
    return cart_response(item, message)


@router.post("/demo/orders/checkout", response_model=DemoOrderResponse)
async def checkout(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoOrderResponse:
    order = await DemoCommerceService().checkout(session, user)
    await session.commit()
    return order_response(order)


@router.get("/demo/orders", response_model=list[DemoOrderResponse])
async def user_orders(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoOrderResponse]:
    orders = (
        await session.scalars(
            select(DemoOrder)
            .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
            .where(DemoOrder.user_id == user.id)
            .order_by(DemoOrder.updated_at.desc())
        )
    ).all()
    return [order_response(item) for item in orders]


@router.get("/demo/orders/{order_id}", response_model=DemoOrderResponse)
async def user_order(
    order_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoOrderResponse:
    return order_response(await DemoCommerceService().get_order(session, user, order_id))


@router.delete("/demo/orders/{order_id}")
async def delete_user_order(
    order_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    order = await session.scalar(
        select(DemoOrder).where(DemoOrder.id == order_id, DemoOrder.user_id == user.id)
    )
    if not order:
        raise HTTPException(404, "Demo sipariş bulunamadı.")
    await session.delete(order)
    await session.commit()
    return {"status": "Demo sipariş silindi."}


@router.post("/demo/reset", response_model=DemoResetResponse)
async def reset_demo(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoResetResponse:
    summary = await DemoCommerceService().reset_user_demo(session, user)
    await session.commit()
    return DemoResetResponse(status="Demo veri hazırlandı.", **summary)


@router.get("/admin/demo/orders", response_model=list[DemoOrderResponse])
async def admin_orders(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoOrderResponse]:
    orders = (
        await session.scalars(
            select(DemoOrder)
            .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
            .order_by(DemoOrder.updated_at.desc())
        )
    ).all()
    return [order_response(item) for item in orders]


@router.patch("/admin/demo/orders/{order_id}", response_model=DemoOrderResponse)
async def update_admin_order(
    order_id: int,
    payload: AdminOrderUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoOrderResponse:
    order = await session.scalar(
        select(DemoOrder)
        .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
        .where(DemoOrder.id == order_id)
    )
    if not order:
        raise HTTPException(404, "Demo sipariş bulunamadı.")
    if payload.order_status:
        order.order_status = payload.order_status
    if payload.payment_status:
        order.payment_status = payload.payment_status
    order.admin_note = payload.admin_note.strip()
    await session.commit()
    await session.refresh(order, ["items", "shipment"])
    return order_response(order)


@router.delete("/admin/demo/orders/{order_id}")
async def delete_admin_order(
    order_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    order = await session.get(DemoOrder, order_id)
    if not order:
        raise HTTPException(404, "Demo sipariş bulunamadı.")
    await session.delete(order)
    await session.commit()
    return {"status": "Demo sipariş silindi."}


@router.patch("/admin/demo/orders/{order_id}/shipment", response_model=DemoOrderResponse)
async def update_admin_shipment(
    order_id: int,
    payload: AdminShipmentUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoOrderResponse:
    order = await session.scalar(
        select(DemoOrder)
        .options(selectinload(DemoOrder.items), selectinload(DemoOrder.shipment))
        .where(DemoOrder.id == order_id)
    )
    if not order:
        raise HTTPException(404, "Demo sipariş bulunamadı.")
    shipment = order.shipment
    if shipment is None:
        shipment = DemoShipment(order_id=order.id)
        session.add(shipment)
        await session.flush()
    shipment.status = payload.shipping_status
    shipment.carrier = payload.carrier
    shipment.tracking_number = payload.tracking_number
    shipment.delay_reason = payload.delay_reason
    shipment.admin_note = payload.admin_note
    shipment.estimated_delivery_at = payload.estimated_delivery_at
    shipment.delivered_at = payload.delivered_at
    order.shipping_status = payload.shipping_status
    await session.commit()
    await session.refresh(order, ["items", "shipment"])
    return order_response(order)


@router.get("/admin/demo/coupons", response_model=list[DemoCouponResponse])
async def admin_coupons(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoCouponResponse]:
    await DemoCommerceService().ensure_seed_data(session)
    coupons = (
        await session.scalars(select(DemoCoupon).order_by(DemoCoupon.code))
    ).all()
    return [coupon_response(item) for item in coupons]


@router.post("/admin/demo/coupons", response_model=DemoCouponResponse)
async def create_admin_coupon(
    payload: AdminCouponCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoCouponResponse:
    coupon = DemoCoupon(**payload.model_dump(), code=payload.code.strip().upper())
    session.add(coupon)
    await session.commit()
    await session.refresh(coupon)
    return coupon_response(coupon)


@router.patch("/admin/demo/coupons/{coupon_id}", response_model=DemoCouponResponse)
async def update_admin_coupon(
    coupon_id: int,
    payload: AdminCouponUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoCouponResponse:
    coupon = await session.get(DemoCoupon, coupon_id)
    if not coupon:
        raise HTTPException(404, "Kupon bulunamadı.")
    for key, value in payload.model_dump().items():
        setattr(coupon, key, value)
    coupon.code = coupon.code.strip().upper()
    await session.commit()
    await session.refresh(coupon)
    return coupon_response(coupon)


@router.delete("/admin/demo/coupons/{coupon_id}")
async def delete_admin_coupon(
    coupon_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    coupon = await session.get(DemoCoupon, coupon_id)
    if not coupon:
        raise HTTPException(404, "Kupon bulunamadı.")
    await session.delete(coupon)
    await session.commit()
    return {"status": "Kupon silindi."}


@router.post("/admin/demo/payment-attempts")
async def create_payment_attempt(
    payload: AdminPaymentAttemptCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    attempt = DemoPaymentAttempt(**payload.model_dump())
    session.add(attempt)
    await session.commit()
    return {"id": attempt.id, "status": "Ödeme denemesi oluşturuldu."}
