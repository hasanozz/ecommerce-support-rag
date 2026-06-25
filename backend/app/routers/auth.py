from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import User, UserSession
from ..schemas.auth import UserResponse
from ..services.auth import AuthService, get_current_user, token_hash
from ..services.privacy import request_ip_hash


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    url, signed_state = AuthService().login_url()
    response = RedirectResponse(url)
    response.set_cookie(
        "oauth_state",
        signed_state,
        max_age=600,
        httponly=True,
        secure=get_settings().app_env != "development",
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    service = AuthService()
    service.validate_state(state, request.cookies.get("oauth_state", ""))
    profile = await service.exchange_code(code)
    user = await service.upsert_user(session, profile)
    raw_token = await service.create_session(
        session,
        user,
        request_ip_hash(request),
        request.headers.get("user-agent", ""),
    )
    settings = get_settings()
    response = RedirectResponse("/")
    response.delete_cookie("oauth_state")
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Response:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        await session.execute(
            update(UserSession)
            .where(UserSession.token_hash == token_hash(raw_token))
            .values(revoked_at=datetime.now(UTC))
        )
        await session.commit()
    response = Response(status_code=204)
    response.delete_cookie(settings.session_cookie_name)
    return response
