"""Authentication endpoints: registration, login, logout, refresh, and current user."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.api.security import (
    create_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_csrf,
    verify_password,
)
from alphalens.config import get_settings
from alphalens.db.models import RefreshToken, User, UserRole
from alphalens.db.session import get_db
from alphalens.logging import get_logger

logger = get_logger("alphalens.auth")
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/csrf", response_model=dict[str, str])
async def get_csrf_token(response: Response, request: Request) -> dict[str, str]:
    """Issue or retrieve double-submit CSRF cookie for initial unauthenticated page loads."""
    existing_cookie = request.cookies.get("csrf_token")
    token = existing_cookie or generate_csrf_token()

    settings = get_settings()
    response.set_cookie(
        key="csrf_token",
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=False,
        secure=settings.app_env == "prod",
        samesite="lax",
        path="/",
    )
    return {"csrf_token": token}


# Request & Response Schemas
class RegisterRequest(BaseModel):
    """User registration payload."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, description="Password must be at least 12 characters")


class LoginRequest(BaseModel):
    """User login payload."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User profile response without sensitive data."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


def _set_auth_cookies(
    response: Response,
    access_token: str,
    raw_refresh_token: str,
    csrf_token: str,
) -> None:
    """Set hardened HTTP cookies for access, refresh, and double-submit CSRF."""
    settings = get_settings()
    is_prod = settings.app_env == "prod"

    # Access Token: Path=/api, HttpOnly
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/api",
    )

    # Refresh Token: Path=/api/auth/refresh, HttpOnly
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/api/auth/refresh",
    )

    # CSRF Token: Path=/, readable by JS for double-submit header
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete all authentication and CSRF cookies."""
    response.delete_cookie(key="access_token", path="/api")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    response.delete_cookie(key="csrf_token", path="/")


@router.post("/register", response_model=UserResponse, dependencies=[Depends(verify_csrf)])
@limiter.limit("3/minute")
async def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user account with Argon2 password hashing."""
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        logger.warn("registration_failed_email_exists", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration could not be completed with this email",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("audit_user_registered", user_id=str(user.id), email=user.email)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(verify_csrf)])
@limiter.limit("5/minute")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Authenticate credentials and issue access, refresh, and CSRF cookies."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        logger.warn("audit_login_failed", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    settings = get_settings()
    access_token = create_access_token(user.id, user.role.value)
    raw_refresh_token, token_hash = generate_refresh_token()
    csrf_token = generate_csrf_token()

    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(refresh_record)
    db.commit()

    _set_auth_cookies(response, access_token, raw_refresh_token, csrf_token)
    logger.info("audit_login_success", user_id=str(user.id), email=user.email)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=dict[str, str], dependencies=[Depends(verify_csrf)])
async def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Rotate refresh token and issue new access token. Detects token reuse."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    token_hash = hash_token(raw_refresh)
    token_record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if not token_record:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # REUSE DETECTION: If an already-revoked refresh token is presented, compromise is assumed
    if token_record.revoked:
        logger.error(
            "audit_refresh_token_reuse_detected",
            user_id=str(token_record.user_id),
            token_id=str(token_record.id),
        )
        # Invalidate ALL sessions for this user immediately
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token_record.user_id)
            .values(revoked=True)
        )
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All sessions revoked for security.",
        )

    # Check expiry (ensure timezone awareness for SQLite compatibility)
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < datetime.now(UTC):
        token_record.revoked = True
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    user = db.scalar(select(User).where(User.id == token_record.user_id))
    if not user or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or removed",
        )

    # ROTATION: Revoke current token and generate replacement
    new_raw_refresh, new_token_hash = generate_refresh_token()
    settings = get_settings()
    new_expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    new_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=new_expires_at,
        revoked=False,
    )
    db.add(new_record)
    db.flush()

    token_record.revoked = True
    token_record.replaced_by = new_record.id
    db.commit()

    new_access_token = create_access_token(user.id, user.role.value)
    new_csrf_token = generate_csrf_token()

    _set_auth_cookies(response, new_access_token, new_raw_refresh, new_csrf_token)
    logger.info("audit_session_refreshed", user_id=str(user.id))
    return {"status": "refreshed"}


@router.post("/logout", response_model=dict[str, str], dependencies=[Depends(verify_csrf)])
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke refresh token and clear all auth cookies."""
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = hash_token(raw_refresh)
        db.execute(
            update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True)
        )
        db.commit()

    _clear_auth_cookies(response)
    logger.info("audit_user_logged_out")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return currently authenticated user profile."""
    return UserResponse.model_validate(current_user)
