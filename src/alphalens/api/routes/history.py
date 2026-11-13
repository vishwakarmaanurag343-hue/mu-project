"""User prediction history endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.db.models import PredictionLog, User
from alphalens.db.session import get_db

router = APIRouter(prefix="/api/history", tags=["history"])


class HistoryItem(BaseModel):
    """User prediction history item."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    ticker: str
    probability: float
    decision_label: str
    model_version: str
    outcome: float | None
    model_horizon_months: int = 6
    created_at: datetime


@router.get("", response_model=list[HistoryItem])
async def get_user_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryItem]:
    """Retrieve paginated list of served predictions for the authenticated user."""
    # Predictions are logged by pseudo_id
    user = db.get(User, current_user.id)
    if not user or not user.pseudonym:
        return []

    pseudo_id = user.pseudonym.pseudo_id
    records = db.scalars(
        select(PredictionLog)
        .where(PredictionLog.pseudo_id == pseudo_id)
        .order_by(PredictionLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        HistoryItem(
            id=r.id,
            ticker=r.ticker,
            probability=r.probability,
            decision_label=r.decision_label,
            model_version=r.model_version,
            outcome=r.outcome,
            model_horizon_months=6,
            created_at=r.created_at,
        )
        for r in records
    ]
