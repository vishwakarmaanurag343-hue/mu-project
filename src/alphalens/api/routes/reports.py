"""Stock equity research reports: instant quant metrics and streamed LLM evidence."""

import asyncio
import json
import re
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from alphalens.api.deps import get_current_user
from alphalens.db.models import User
from alphalens.db.session import get_db
from alphalens.engine.quant import QuantReportResponse, get_precomputed_quant_score
from alphalens.llm.evidence import get_verified_evidence_claims

router = APIRouter(prefix="/api/reports", tags=["reports"])
limiter = Limiter(key_func=get_remote_address)

TICKER_REGEX = re.compile(r"^[A-Z0-9_\-&]+\.NS$")


def validate_ticker(ticker: str) -> str:
    """Validate NSE ticker format."""
    normalized = ticker.strip().upper()
    if not TICKER_REGEX.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid NSE ticker format. Must end with .NS suffix (e.g. RELIANCE.NS)",
        )
    return normalized


@router.get("/{ticker}/quant", response_model=QuantReportResponse)
async def get_quant_report(
    ticker: str = Path(description="NSE Ticker symbol"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuantReportResponse:
    """Retrieve precomputed quantitative metrics from local store (instant, <300ms).

    Deliberately decoupled from any live fetch or LLM processing.
    """
    valid_ticker = validate_ticker(ticker)
    return get_precomputed_quant_score(valid_ticker, current_user, db)


@router.get("/{ticker}/evidence/stream")
@limiter.limit("10/hour")
async def stream_evidence_report(
    request: Request,
    ticker: str = Path(description="NSE Ticker symbol"),
    current_user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """Stream verified LLM evidence statements via Server-Sent Events (SSE)."""
    valid_ticker = validate_ticker(ticker)

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        try:
            # 1. Status event: Extraction
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "stage": "extracting",
                        "message": f"Analyzing quarterly filings for {valid_ticker}...",
                    }
                ),
            }
            await asyncio.sleep(0.05)

            # 2. Status event: Verification
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "stage": "verifying",
                        "message": "Verifying cross-source regulatory citations...",
                    }
                ),
            }
            await asyncio.sleep(0.05)

            # 3. Stream verified claims
            claims = get_verified_evidence_claims(valid_ticker)
            for claim in claims:
                yield {
                    "event": "claim",
                    "data": claim.model_dump_json(),
                }
                await asyncio.sleep(0.05)

            # 4. Done event
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "total_claims": len(claims),
                        "cached": True,
                        "ticker": valid_ticker,
                    }
                ),
            }

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "pipeline_error",
                        "message": f"Evidence streaming error: {exc!s}",
                    }
                ),
            }

    return EventSourceResponse(event_generator())
