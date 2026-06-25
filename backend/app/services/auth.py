from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..database import get_db
from ..models import User, UserSession


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.serializer = URLSafeTimedSerializer(
            self.settings.session_secret.get_secret_value(),
            salt="google-oauth-state",
        )

    def login_url(self) -> tuple[str, str]:
        if not self.settings.google_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth yapılandırılmamış.",
            )
        state = secrets.token_urlsafe(24)
        signed_state = self.serializer.dumps(state)
        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}", signed_state

    def validate_state(self, state: str, signed_state: str) -> None:
        try:
            expected = self.serializer.loads(signed_state, max_age=600)
        except BadSignature as exc:
            raise HTTPException(status_code=400, detail="Geçersiz OAuth state.") from exc
        if not secrets.compare_digest(state, expected):
            raise HTTPException(status_code=400, detail="OAuth state eşleşmedi.")

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret.get_secret_value(),
                    "redirect_uri": self.settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]
            user_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_response.raise_for_status()
            return user_response.json()

    async def upsert_user(self, session: AsyncSession, profile: dict) -> User:
        if profile.get("email_verified") is False:
            raise HTTPException(status_code=403, detail="Google e-postası doğrulanmamış.")
        google_sub = str(profile["sub"])
        email = str(profile["email"]).casefold()
        user = await session.scalar(select(User).where(User.google_sub == google_sub))
        is_admin = email in {item.casefold() for item in self.settings.admin_emails}
        if user is None:
            user = User(
                google_sub=google_sub,
                email=email,
                display_name=str(profile.get("name", "")),
                avatar_url=profile.get("picture"),
                is_admin=is_admin,
            )
            session.add(user)
            await session.flush()
        else:
            user.email = email
            user.display_name = str(profile.get("name", user.display_name))
            user.avatar_url = profile.get("picture", user.avatar_url)
            user.is_admin = is_admin
            user.last_login_at = datetime.now(UTC)
        return user

    async def create_session(
        self,
        session: AsyncSession,
        user: User,
        ip_hash: str,
        user_agent: str,
    ) -> str:
        raw_token = secrets.token_urlsafe(48)
        session.add(
            UserSession(
                user_id=user.id,
                token_hash=token_hash(raw_token),
                ip_hash=ip_hash,
                user_agent=user_agent[:500],
                expires_at=datetime.now(UTC)
                + timedelta(hours=self.settings.session_ttl_hours),
            )
        )
        await session.commit()
        return raw_token


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor.")
    db_session = await session.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash(raw_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    if db_session is None:
        raise HTTPException(status_code=401, detail="Oturum geçersiz veya süresi dolmuş.")
    user = await session.get(User, db_session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekiyor.")
    return user
