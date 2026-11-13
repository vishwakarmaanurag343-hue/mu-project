"""User profile management and Delete-My-Data privacy endpoints."""

import shutil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.api.security import verify_csrf, verify_password
from alphalens.config import get_settings
from alphalens.db.models import (
    AuditLog,
    ConsentRecord,
    PendingDeletion,
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
    """Confirmation payload requiring current password and exact string 'DELETE'."""

    model_config = ConfigDict(extra="forbid")

    password: str
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


def process_pending_deletions(db: Session) -> int:
    """Retry function to clean up pending deletions recorded during failures."""
    pending_items = db.scalars(select(PendingDeletion)).all()
    cleaned_count = 0
    settings = get_settings()

    for item in pending_items:
        try:
            if item.resource_type == "file":
                file_path = settings.upload_dir / item.resource_identifier
                if file_path.is_file():
                    file_path.unlink()
            elif item.resource_type == "vector":
                vector_path = settings.cache_dir / "vectors" / item.resource_identifier
                if vector_path.is_dir():
                    shutil.rmtree(vector_path)
            db.delete(item)
            cleaned_count += 1
        except Exception as e:
            item.retry_count += 1
            item.error_message = str(e)
            logger.warning("pending_deletion_retry_failed", id=str(item.id), error=str(e))

    db.commit()
    return cleaned_count


@router.delete("/api/me/data", response_model=dict[str, str], dependencies=[Depends(verify_csrf)])
async def delete_my_data(
    payload: DeleteDataRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Permanently delete user account, uploaded documents, and pseudonymise predictions.

    Requires current password (wrong password -> 403) and exact string 'DELETE' in body.
    Database deletions occur in one atomic transaction first; files/vectors cleaned post-tx.
    Any filesystem/vector deletion failures are recorded in pending_deletions.
    """
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect password. Account deletion prohibited.",
        )

    if payload.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required: You must provide exact string 'DELETE'",
        )

    settings = get_settings()
    user_id = current_user.id

    # Lookup or ensure pseudonym
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    pseudo_id = user.pseudonym.pseudo_id if user.pseudonym else None

    # Retrieve files to delete post-transaction
    user_uploads = db.scalars(select(UploadRecord).where(UploadRecord.user_id == user_id)).all()
    files_to_delete = [up.stored_filename for up in user_uploads]

    # --- 1. Database deletions & updates in ONE transaction ---
    # a. Audit log sanitisation: replace user identifiers (email, user_id) with pseudo_id, strip IP
    db.execute(
        update(AuditLog)
        .where(AuditLog.user_id == user_id)
        .values(
            user_id=None,
            email=None,
            pseudo_id=pseudo_id,
            ip_address=None,
        )
    )

    # b. ConsentRecord pseudonymisation: replace user_id with pseudo_id as proof of consent
    db.execute(
        update(ConsentRecord)
        .where(ConsentRecord.user_id == user_id)
        .values(
            user_id=None,
            pseudo_id=pseudo_id,
        )
    )

    # c. Delete user from DB (cascades pseudonym, profile, refresh_tokens, uploads)
    db.delete(user)
    db.commit()

    # --- 2. Filesystem & vector deletions post-transaction ---
    # Track any failure in pending_deletions table
    for filename in files_to_delete:
        file_path = settings.upload_dir / filename
        try:
            if file_path.is_file():
                file_path.unlink()
        except Exception as e:
            logger.error("file_deletion_failed_queued_for_retry", file=filename, error=str(e))
            pending = PendingDeletion(
                user_id=user_id,
                resource_type="file",
                resource_identifier=filename,
                error_message=str(e),
            )
            db.add(pending)

    user_vector_dir = settings.cache_dir / "vectors" / str(user_id)
    try:
        if user_vector_dir.is_dir():
            shutil.rmtree(user_vector_dir)
    except Exception as e:
        logger.error("vector_deletion_failed_queued_for_retry", user_id=str(user_id), error=str(e))
        pending = PendingDeletion(
            user_id=user_id,
            resource_type="vector",
            resource_identifier=str(user_id),
            error_message=str(e),
        )
        db.add(pending)

    db.commit()

    # --- 3. Clear authentication cookies ---
    response.delete_cookie(key="access_token", path="/api")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    response.delete_cookie(key="csrf_token", path="/")

    logger.info("audit_user_data_deleted_and_pseudonymised", pseudo_id=str(pseudo_id))
    return {"status": "deleted", "message": "Account deleted and prediction records pseudonymised"}
