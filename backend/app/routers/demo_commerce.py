from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..models import (
    DemoCart,
    DemoCartItem,
    DemoCoupon,
    DemoOrder,
    DemoPaymentAttempt,
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
from ..schemas.demo_commerce import (
    AdminCouponCreate,
    AdminCouponUpdate,
    AdminDemoProductResponse,
    AdminDemoReviewResponse,
    AdminOrderUpdate,
    AdminReturnRequestUpdate,
    AdminPaymentAttemptCreate,
    AdminShipmentUpdate,
    CartItemCreate,
    CartItemUpdate,
    CouponApplyRequest,
    DemoCartItemResponse,
    DemoCartResponse,
    DemoCouponResponse,
    DemoFavoriteResponse,
    DemoOrderItemResponse,
    DemoOrderResponse,
    DemoProductDetailResponse,
    DemoProductResponse,
    DemoProductReviewResponse,
    DemoProductReviewUpsert,
    DemoResetResponse,
    DemoReturnRequestResponse,
    DemoRefundResponse,
    DemoScenarioResponse,
    DemoSavedCardResponse,
    DemoShipmentResponse,
    DemoSecurityProfileResponse,
    DemoWalletResponse,
)
from ..services.auth import get_current_user, require_admin
from ..services.demo_commerce import DemoCommerceService
from ..services.demo_seed import DemoSeedService


router = APIRouter(prefix="/api", tags=["demo-commerce"])


def _rating_value(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def product_stats(
    session: AsyncSession, product_ids: list[int], user: User | None = None
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
        stats[product_id]["rating_average"] = _rating_value(rating_average)
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
    return stats


def product_response(product: DemoProduct, stats: dict | None = None) -> DemoProductResponse:
    stats = stats or {}
    return DemoProductResponse(
        id=product.id,
        sku=product.sku,
        name=product.name,
        brand=product.brand,
        category=product.category,
        subcategory=product.subcategory,
        price=product.price,
        currency=product.currency,
        stock=product.stock,
        is_active=product.is_active,
        image_url=product.image_url,
        image_urls=product.image_urls or [],
        description=product.description,
        returnable=product.returnable,
        warranty_months=product.warranty_months,
        tags=product.tags or [],
        rating_average=stats.get("rating_average"),
        review_count=stats.get("review_count", 0),
        favorite_count=stats.get("favorite_count", 0),
        is_favorited=stats.get("is_favorited", False),
    )


def review_response(
    review: DemoProductReview,
    user: User,
    current_user: User | None = None,
) -> DemoProductReviewResponse:
    return DemoProductReviewResponse(
        id=review.id,
        product_id=review.product_id,
        user_id=review.user_id,
        user_display_name=user.display_name or user.email,
        rating=review.rating,
        title=review.title,
        body=review.body,
        is_verified_purchase=review.is_verified_purchase,
        is_visible=review.is_visible,
        is_own_review=bool(current_user and current_user.id == review.user_id),
        created_at=review.created_at,
        updated_at=review.updated_at,
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


def refund_response(refund: DemoRefund | None) -> DemoRefundResponse | None:
    if refund is None:
        return None
    return DemoRefundResponse(
        id=refund.id,
        refund_status=refund.refund_status,
        refund_amount=refund.refund_amount,
        refund_reference=refund.refund_reference,
        refund_reason=refund.refund_reason,
        initiated_at=refund.initiated_at,
        completed_at=refund.completed_at,
    )


def return_request_response(
    return_request: DemoReturnRequest | None,
) -> DemoReturnRequestResponse | None:
    if return_request is None:
        return None
    product_name = ""
    if return_request.order and return_request.order.items:
        product_name = ", ".join(
            item.product_name for item in return_request.order.items[:2] if item.product_name
        )
    return DemoReturnRequestResponse(
        id=return_request.id,
        order_id=return_request.order_id,
        order_no=return_request.order.order_no if return_request.order else "",
        product_name=product_name,
        user_id=return_request.user_id,
        return_request=return_request.return_request,
        return_code=return_request.return_code,
        return_status=return_request.return_status,
        refund_status=return_request.refund_status,
        return_reason=return_request.return_reason,
        return_tracking_no=return_request.return_tracking_no,
        refund=refund_response(return_request.refund),
        created_at=return_request.created_at,
        updated_at=return_request.updated_at,
    )


def return_code_for_order(order: DemoOrder) -> str:
    safe_order_no = "".join(ch for ch in order.order_no.upper() if ch.isalnum())
    return f"RET-{safe_order_no or order.id}"


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
        return_request=return_request_response(order.return_request),
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


def wallet_response(wallet: DemoWallet) -> DemoWalletResponse:
    return DemoWalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        balance=wallet.balance,
        currency=wallet.currency,
        status=wallet.status,
        updated_at=wallet.updated_at,
    )


def saved_card_response(card: DemoSavedCard) -> DemoSavedCardResponse:
    return DemoSavedCardResponse(
        id=card.id,
        user_id=card.user_id,
        card_token=card.card_token,
        card_brand=card.card_brand,
        last4=card.last4,
        holder_name=card.holder_name,
        is_default=card.is_default,
        is_active=card.is_active,
        expiry_month=card.expiry_month,
        expiry_year=card.expiry_year,
        created_at=card.created_at,
    )


def security_profile_response(
    profile: DemoUserSecurityProfile,
) -> DemoSecurityProfileResponse:
    return DemoSecurityProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        security_status=profile.security_status,
        suspicious_login_count=profile.suspicious_login_count,
        email_verified_required=profile.email_verified_required,
        phone_verified_required=profile.phone_verified_required,
        password_change_recommended=profile.password_change_recommended,
        risk_note=profile.risk_note,
        updated_at=profile.updated_at,
    )


@router.get("/demo/products", response_model=list[DemoProductResponse])
async def products(
    q: str = Query(default=""),
    category: str = Query(default=""),
    subcategory: str = Query(default=""),
    brand: str = Query(default=""),
    min_price: Decimal | None = Query(default=None),
    max_price: Decimal | None = Query(default=None),
    in_stock: bool | None = Query(default=None),
    sort: str = Query(default="name"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoProductResponse]:
    service = DemoCommerceService()
    await service.ensure_seed_data(session)
    query = select(DemoProduct).where(DemoProduct.is_active.is_(True))
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                DemoProduct.name.ilike(pattern),
                DemoProduct.brand.ilike(pattern),
                DemoProduct.category.ilike(pattern),
                DemoProduct.subcategory.ilike(pattern),
                DemoProduct.search_text.ilike(pattern),
            )
        )
    if category.strip():
        query = query.where(DemoProduct.category == category.strip())
    if subcategory.strip():
        query = query.where(DemoProduct.subcategory == subcategory.strip())
    if brand.strip():
        query = query.where(DemoProduct.brand == brand.strip())
    if min_price is not None:
        query = query.where(DemoProduct.price >= min_price)
    if max_price is not None:
        query = query.where(DemoProduct.price <= max_price)
    if in_stock is True:
        query = query.where(DemoProduct.stock > 0)
    if sort == "price_asc":
        query = query.order_by(DemoProduct.price.asc(), DemoProduct.name)
    elif sort == "price_desc":
        query = query.order_by(DemoProduct.price.desc(), DemoProduct.name)
    else:
        query = query.order_by(DemoProduct.category, DemoProduct.name)
    items = (await session.scalars(query.offset(offset).limit(limit))).all()
    stats = await product_stats(session, [item.id for item in items], user)
    if sort == "rating_desc":
        items = sorted(
            items,
            key=lambda item: stats[item.id]["rating_average"] or Decimal("-1"),
            reverse=True,
        )
    return [product_response(item, stats.get(item.id)) for item in items]


@router.get("/demo/products/{product_id}", response_model=DemoProductDetailResponse)
async def product_detail(
    product_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoProductDetailResponse:
    product = await session.get(DemoProduct, product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Ürün bulunamadı.")
    stats = await product_stats(session, [product.id], user)
    review_rows = (
        await session.execute(
            select(DemoProductReview, User)
            .join(User, User.id == DemoProductReview.user_id)
            .where(
                DemoProductReview.product_id == product.id,
                DemoProductReview.is_visible.is_(True),
            )
            .order_by(DemoProductReview.updated_at.desc())
            .limit(20)
        )
    ).all()
    base = product_response(product, stats.get(product.id)).model_dump()
    return DemoProductDetailResponse(
        **base,
        attributes=product.attributes or {},
        return_policy_note=product.return_policy_note,
        warranty_note=product.warranty_note,
        reviews=[
            review_response(review, review_user, user)
            for review, review_user in review_rows
        ],
    )


@router.get(
    "/demo/products/{product_id}/reviews",
    response_model=list[DemoProductReviewResponse],
)
async def product_reviews(
    product_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoProductReviewResponse]:
    product = await session.get(DemoProduct, product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Ürün bulunamadı.")
    rows = (
        await session.execute(
            select(DemoProductReview, User)
            .join(User, User.id == DemoProductReview.user_id)
            .where(
                DemoProductReview.product_id == product_id,
                DemoProductReview.is_visible.is_(True),
            )
            .order_by(DemoProductReview.updated_at.desc())
        )
    ).all()
    return [review_response(review, review_user, user) for review, review_user in rows]


@router.post(
    "/demo/products/{product_id}/reviews",
    response_model=DemoProductReviewResponse,
)
async def upsert_product_review(
    product_id: int,
    payload: DemoProductReviewUpsert,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoProductReviewResponse:
    product = await session.get(DemoProduct, product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Ürün bulunamadı.")
    if payload.rating is None and not payload.title.strip() and not payload.body.strip():
        raise HTTPException(400, "Puan veya yorum içeriği gerekli.")
    review = await session.scalar(
        select(DemoProductReview).where(
            DemoProductReview.product_id == product_id,
            DemoProductReview.user_id == user.id,
        )
    )
    if review is None:
        review = DemoProductReview(product_id=product_id, user_id=user.id)
        session.add(review)
    review.rating = payload.rating
    review.title = payload.title.strip()
    review.body = payload.body.strip()
    review.is_visible = True
    await session.commit()
    await session.refresh(review)
    return review_response(review, user, user)


@router.get("/demo/favorites", response_model=list[DemoFavoriteResponse])
async def favorites(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoFavoriteResponse]:
    rows = (
        await session.scalars(
            select(DemoProductFavorite)
            .options(selectinload(DemoProductFavorite.product))
            .where(DemoProductFavorite.user_id == user.id)
            .order_by(DemoProductFavorite.created_at.desc())
        )
    ).all()
    stats = await product_stats(session, [item.product_id for item in rows], user)
    return [
        DemoFavoriteResponse(
            id=item.id,
            product=product_response(item.product, stats.get(item.product_id)),
            created_at=item.created_at,
        )
        for item in rows
        if item.product and item.product.is_active
    ]


@router.post("/demo/favorites/{product_id}", response_model=DemoFavoriteResponse)
async def add_favorite(
    product_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoFavoriteResponse:
    product = await session.get(DemoProduct, product_id)
    if not product or not product.is_active:
        raise HTTPException(404, "Ürün bulunamadı.")
    favorite = await session.scalar(
        select(DemoProductFavorite).where(
            DemoProductFavorite.product_id == product_id,
            DemoProductFavorite.user_id == user.id,
        )
    )
    if favorite is None:
        favorite = DemoProductFavorite(user_id=user.id, product_id=product_id)
        session.add(favorite)
        await session.commit()
        await session.refresh(favorite)
    stats = await product_stats(session, [product.id], user)
    return DemoFavoriteResponse(
        id=favorite.id,
        product=product_response(product, stats.get(product.id)),
        created_at=favorite.created_at,
    )


@router.delete("/demo/favorites/{product_id}")
async def remove_favorite(
    product_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    favorite = await session.scalar(
        select(DemoProductFavorite).where(
            DemoProductFavorite.product_id == product_id,
            DemoProductFavorite.user_id == user.id,
        )
    )
    if favorite is not None:
        await session.delete(favorite)
        await session.commit()
    return {"status": "Favori kaldırıldı."}


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
            .options(
                selectinload(DemoOrder.items),
                selectinload(DemoOrder.shipment),
                selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
                selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.order),
            )
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


@router.post("/demo/orders/{order_id}/return", response_model=DemoReturnRequestResponse)
async def create_user_return_request(
    order_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoReturnRequestResponse:
    order = await session.scalar(
        select(DemoOrder)
        .options(
            selectinload(DemoOrder.items),
            selectinload(DemoOrder.shipment),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.order),
        )
        .where(DemoOrder.id == order_id, DemoOrder.user_id == user.id)
    )
    if not order:
        raise HTTPException(404, "Demo sipariş bulunamadı.")
    if order.return_request:
        return return_request_response(order.return_request)
    if order.order_status == "CANCELLED":
        raise HTTPException(400, "İptal edilmiş sipariş için iade talebi oluşturulamaz.")
    if order.payment_status == "FAILED":
        raise HTTPException(400, "Ödemesi başarısız sipariş için iade talebi oluşturulamaz.")

    return_request = DemoReturnRequest(
        order_id=order.id,
        user_id=user.id,
        return_request="CREATED",
        return_code=return_code_for_order(order),
        return_status="CREATED",
        refund_status="PENDING",
        return_reason="Kullanıcı Siparişlerim ekranından iade talebi oluşturdu.",
        return_tracking_no=f"RTN-{order.order_no.replace('-', '')}",
    )
    order.order_status = "REFUND_PENDING"
    order.payment_status = "REFUND_PENDING"
    session.add(return_request)
    await session.commit()
    await session.refresh(return_request, ["refund", "order"])
    return return_request_response(return_request)


@router.get("/demo/returns", response_model=list[DemoReturnRequestResponse])
async def user_returns(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoReturnRequestResponse]:
    rows = (
        await session.scalars(
            select(DemoReturnRequest)
            .options(
                selectinload(DemoReturnRequest.refund),
                selectinload(DemoReturnRequest.order).selectinload(DemoOrder.items),
            )
            .where(DemoReturnRequest.user_id == user.id)
            .order_by(DemoReturnRequest.updated_at.desc())
        )
    ).all()
    return [return_request_response(item) for item in rows if item]


@router.get("/demo/wallet", response_model=DemoWalletResponse | None)
async def user_wallet(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoWalletResponse | None:
    wallet = await session.scalar(select(DemoWallet).where(DemoWallet.user_id == user.id))
    return wallet_response(wallet) if wallet else None


@router.get("/demo/cards", response_model=list[DemoSavedCardResponse])
async def user_cards(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoSavedCardResponse]:
    rows = (
        await session.scalars(
            select(DemoSavedCard)
            .where(DemoSavedCard.user_id == user.id)
            .order_by(DemoSavedCard.is_default.desc(), DemoSavedCard.created_at.desc())
        )
    ).all()
    return [saved_card_response(item) for item in rows]


@router.get("/demo/security", response_model=DemoSecurityProfileResponse | None)
async def user_security_profile(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoSecurityProfileResponse | None:
    profile = await session.scalar(
        select(DemoUserSecurityProfile).where(DemoUserSecurityProfile.user_id == user.id)
    )
    return security_profile_response(profile) if profile else None


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


@router.post("/demo/scenarios/{scenario_key}/prepare", response_model=DemoScenarioResponse)
async def prepare_demo_scenario(
    scenario_key: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoScenarioResponse:
    try:
        result = await DemoSeedService().prepare_demo_scenario(
            session, user, scenario_key
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    await session.commit()
    return DemoScenarioResponse(**result)


@router.get("/demo/scenarios", response_model=list[DemoScenarioResponse])
async def demo_scenarios(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DemoScenarioResponse]:
    rows = await DemoSeedService().demo_scenario_statuses(session, user)
    return [DemoScenarioResponse(**item) for item in rows]


@router.post("/demo/scenarios/{scenario_key}/clear", response_model=DemoScenarioResponse)
async def clear_demo_scenario(
    scenario_key: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemoScenarioResponse:
    try:
        result = await DemoSeedService().clear_demo_scenario(
            session, user, scenario_key
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    await session.commit()
    return DemoScenarioResponse(**result)


@router.get("/admin/demo/products", response_model=list[AdminDemoProductResponse])
async def admin_products(
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[AdminDemoProductResponse]:
    await DemoCommerceService().ensure_seed_data(session)
    items = (
        await session.scalars(select(DemoProduct).order_by(DemoProduct.category, DemoProduct.name))
    ).all()
    stats = await product_stats(session, [item.id for item in items], admin)
    return [
        AdminDemoProductResponse(
            **product_response(item, stats.get(item.id)).model_dump(),
            attributes=item.attributes or {},
            return_policy_note=item.return_policy_note,
            warranty_note=item.warranty_note,
            reviews=[],
            search_text=item.search_text,
            ai_context=item.ai_context,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/admin/demo/products/{product_id}", response_model=AdminDemoProductResponse)
async def admin_product_detail(
    product_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminDemoProductResponse:
    product = await session.get(DemoProduct, product_id)
    if not product:
        raise HTTPException(404, "Ürün bulunamadı.")
    stats = await product_stats(session, [product.id], admin)
    review_rows = (
        await session.execute(
            select(DemoProductReview, User)
            .join(User, User.id == DemoProductReview.user_id)
            .where(DemoProductReview.product_id == product.id)
            .order_by(DemoProductReview.updated_at.desc())
        )
    ).all()
    return AdminDemoProductResponse(
        **product_response(product, stats.get(product.id)).model_dump(),
        attributes=product.attributes or {},
        return_policy_note=product.return_policy_note,
        warranty_note=product.warranty_note,
        reviews=[
            review_response(review, review_user, admin)
            for review, review_user in review_rows
        ],
        search_text=product.search_text,
        ai_context=product.ai_context,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/admin/demo/reviews", response_model=list[AdminDemoReviewResponse])
async def admin_reviews(
    product_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    is_visible: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[AdminDemoReviewResponse]:
    query = (
        select(DemoProductReview, DemoProduct, User)
        .join(DemoProduct, DemoProduct.id == DemoProductReview.product_id)
        .join(User, User.id == DemoProductReview.user_id)
    )
    if product_id is not None:
        query = query.where(DemoProductReview.product_id == product_id)
    if user_id is not None:
        query = query.where(DemoProductReview.user_id == user_id)
    if is_visible is not None:
        query = query.where(DemoProductReview.is_visible.is_(is_visible))
    rows = (await session.execute(query.order_by(DemoProductReview.updated_at.desc()))).all()
    return [
        AdminDemoReviewResponse(
            **review_response(review, review_user, admin).model_dump(),
            product_name=product.name,
            user_email=review_user.email,
        )
        for review, product, review_user in rows
    ]


@router.post("/admin/demo/users/{user_id}/reset", response_model=DemoResetResponse)
async def reset_user_demo_admin(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoResetResponse:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
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
            .options(
                selectinload(DemoOrder.items),
                selectinload(DemoOrder.shipment),
                selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
                selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.order),
            )
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
        .options(
            selectinload(DemoOrder.items),
            selectinload(DemoOrder.shipment),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.order),
        )
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
    await session.refresh(order, ["items", "shipment", "return_request"])
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
        .options(
            selectinload(DemoOrder.items),
            selectinload(DemoOrder.shipment),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.refund),
            selectinload(DemoOrder.return_request).selectinload(DemoReturnRequest.order),
        )
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
    await session.refresh(order, ["items", "shipment", "return_request"])
    return order_response(order)


@router.get("/admin/demo/returns", response_model=list[DemoReturnRequestResponse])
async def admin_returns(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoReturnRequestResponse]:
    rows = (
        await session.scalars(
            select(DemoReturnRequest)
            .options(selectinload(DemoReturnRequest.refund), selectinload(DemoReturnRequest.order))
            .order_by(DemoReturnRequest.updated_at.desc())
        )
    ).all()
    return [return_request_response(item) for item in rows if item]


@router.patch("/admin/demo/returns/{return_id}", response_model=DemoReturnRequestResponse)
async def update_admin_return(
    return_id: int,
    payload: AdminReturnRequestUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DemoReturnRequestResponse:
    return_request = await session.scalar(
        select(DemoReturnRequest)
        .options(selectinload(DemoReturnRequest.refund), selectinload(DemoReturnRequest.order))
        .where(DemoReturnRequest.id == return_id)
    )
    if not return_request:
        raise HTTPException(404, "İade kaydı bulunamadı.")
    for key, value in payload.model_dump(exclude_none=True).items():
        if key == "refund_reference":
            if return_request.refund is None:
                return_request.refund = DemoRefund(return_request_id=return_request.id)
            return_request.refund.refund_reference = value
        elif key == "refund_amount":
            if return_request.refund is None:
                return_request.refund = DemoRefund(return_request_id=return_request.id)
            return_request.refund.refund_amount = value
        elif key == "refund_reason":
            if return_request.refund is None:
                return_request.refund = DemoRefund(return_request_id=return_request.id)
            return_request.refund.refund_reason = value
        elif key == "refund_status":
            return_request.refund_status = value
            if return_request.refund is None:
                return_request.refund = DemoRefund(return_request_id=return_request.id)
            return_request.refund.refund_status = value
        else:
            setattr(return_request, key, value)
    await session.commit()
    await session.refresh(return_request, ["refund", "order"])
    return return_request_response(return_request)


@router.get("/admin/demo/wallets", response_model=list[DemoWalletResponse])
async def admin_wallets(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoWalletResponse]:
    rows = (await session.scalars(select(DemoWallet).order_by(DemoWallet.updated_at.desc()))).all()
    return [wallet_response(item) for item in rows]


@router.get("/admin/demo/cards", response_model=list[DemoSavedCardResponse])
async def admin_cards(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoSavedCardResponse]:
    rows = (
        await session.scalars(
            select(DemoSavedCard)
            .order_by(DemoSavedCard.is_default.desc(), DemoSavedCard.created_at.desc())
        )
    ).all()
    return [saved_card_response(item) for item in rows]


@router.get("/admin/demo/security-profiles", response_model=list[DemoSecurityProfileResponse])
async def admin_security_profiles(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DemoSecurityProfileResponse]:
    rows = (
        await session.scalars(
            select(DemoUserSecurityProfile).order_by(DemoUserSecurityProfile.updated_at.desc())
        )
    ).all()
    return [security_profile_response(item) for item in rows]


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
