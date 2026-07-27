"""App-level login for deployed dashboard access."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_session_token, current_session, hash_password, verify_password
from app.core.config import get_settings
from app.db.models import AppUserModel
from app.db.session import get_db

router = APIRouter(prefix="/auth/app", tags=["app-auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = None
    invite_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


def _set_session_cookie(response: Response, user: AppUserModel) -> None:
    settings = get_settings()
    token = create_session_token(str(user.id), user.email)
    response.set_cookie(
        settings.app_session_cookie_name,
        token,
        httponly=True,
        secure=settings.app_auth_enabled,
        samesite="lax",
        max_age=settings.app_session_ttl_minutes * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().app_session_cookie_name, path="/")


async def _user_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(AppUserModel))).scalar_one())


@router.get("/status")
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    session = current_session(request)
    return {
        "auth_enabled": settings.app_auth_enabled,
        "signup_enabled": settings.app_signup_enabled,
        "signup_requires_invite": bool(settings.app_signup_invite_code),
        "has_users": bool(await _user_count(db)),
        "authenticated": bool(session) or not settings.app_auth_enabled,
        "email": session.get("email") if session else None,
    }


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    if not settings.app_signup_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signup is disabled.")
    if settings.app_signup_invite_code and payload.invite_code != settings.app_signup_invite_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid invite code.")
    if settings.app_allowed_email and payload.email.lower() != settings.app_allowed_email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not allowed for this app.")
    existing = await db.execute(select(AppUserModel).where(AppUserModel.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")

    user = AppUserModel(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_admin=(await _user_count(db)) == 0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, user)
    return {"status": "created", "email": user.email, "user_id": str(user.id)}


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await db.execute(select(AppUserModel).where(AppUserModel.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, user)
    return {"status": "ok", "email": user.email, "user_id": str(user.id)}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    _clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
async def me(request: Request) -> dict[str, object]:
    settings = get_settings()
    session = current_session(request)
    if not session and settings.app_auth_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return {"authenticated": bool(session) or not settings.app_auth_enabled, "email": session.get("email") if session else None}
