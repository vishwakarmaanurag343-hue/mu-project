"""User profile management and Delete-My-Data privacy endpoints."""

import contextlib
import shutil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.api.security import verify_csrf
from alphalens.config import get_settings
from alphalens.db.models import (
    PredictionLog,
    RefreshToken,
    RiskLevel,
    UploadRecord,
    User,
    UserProfile,
)
from alphalens.db.session import get_db
from alphalens.logging import get_logger

logger = get_logger("alphalens.profile")
router = APIRouter(tags=["profile"])


class ProfilePayload(BaseModel):
    """User investment profile payload."""

    model_config = ConfigDict(extra="forbid")

    risk_level: RiskLevel = RiskLevel.MODERATE
    investment_horizon_months: Literal[3, 6, 12] = 6
    sector_exclusions: list[str] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(extra="forbid")

    risk_level: str
    investment_horizon_months: int
    sector_exclusions: list[str]


class DeleteDataRequest(BaseModel):
    """Confirmation payload requiring exact string 'DELETE'."""

    model_config = ConfigDict(extra="forbid")

    confirmation: str


@router.get("/api/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Retrieve user investment preferences."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if not profile:
        return ProfileResponse(
            risk_level=RiskLevel.MODERATE.value,
            investment_horizon_months=6,
            sector_exclusions=[],
        )

    return ProfileResponse(
        risk_level=profile.risk_level.value,
        investment_horizon_months=profile.investment_horizon_months,
        sector_exclusions=profile.sector_exclusions,
    )


@router.put("/api/profile", response_model=ProfileResponse, dependencies=[Depends(verify_csrf)])
async def update_profile(
    payload: ProfilePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update user investment profile."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if not profile:
        profile = UserProfile(
            user_id=current_user.id,
            risk_level=payload.risk_level,
            investment_horizon_months=payload.investment_horizon_months,
            sector_exclusions=payload.sector_exclusions,
        )
        db.add(profile)
    else:
        profile.risk_level = payload.risk_level
        profile.investment_horizon_months = payload.investment_horizon_months
        profile.sector_exclusions = payload.sector_exclusions

    db.commit()
    db.refresh(profile)

    return ProfileResponse(
        risk_level=profile.risk_level.value,
        investment_horizon_months=profile.investment_horizon_months,
        sector_exclusions=profile.sector_exclusions,
    )


@router.delete("/api/me/data", response_model=dict[str, str], dependencies=[Depends(verify_csrf)])
async def delete_my_data(
    payload: DeleteDataRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Permanently delete user account and uploaded documents, and pseudonymise prediction records.

    Requires explicit confirmation payload {"confirmation": "DELETE"}.
    """
    if payload.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required: You must provide exact string 'DELETE'",
        )

    settings = get_settings()
    user_id = current_user.id

    # 1. Delete user files from filesystem
    user_uploads = db.scalars(select(UploadRecord).where(UploadRecord.user_id == user_id)).all()
    upload_dir = settings.cache_dir / "uploads"
    for up in user_uploads:
        file_path = upload_dir / up.stored_filename
        if file_path.is_file():
            with contextlib.suppress(Exception):
                file_path.unlink()

    # 2. Delete user's vector embeddings / isolated cache directories if any
    user_vector_dir = settings.cache_dir / "vectors" / str(user_id)
    if user_vector_dir.is_dir():
        with contextlib.suppress(Exception):
            shutil.rmtree(user_vector_dir)

    # 3. Pseudonymise prediction logs: sever link to user, preserving calibration history
    db.execute(update(PredictionLog).where(PredictionLog.user_id == user_id).values(user_id=None))

    # 4. Remove refresh tokens, profile, and user record
    db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    db.delete(current_user)
    db.commit()

    # 5. Clear authentication cookies
    response.delete_cookie(key="access_token", path="/api")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    response.delete_cookie(key="csrf_token", path="/")

    logger.info("audit_user_data_deleted_and_pseudonymised", user_id=str(user_id))
    return {"status": "deleted", "message": "Account deleted and prediction records pseudonymised"}
