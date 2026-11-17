"""Stock equity research reports: instant quant metrics and streamed LLM evidence."""

import asyncio
import json
import re
from collections.abc import AsyncGenerator

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from alphalens.api.deps import get_current_user
from alphalens.db.models import User
from alphalens.db.session import get_db
from alphalens.engine.econometrics import compute_quantitative_diagnostics
from alphalens.engine.quant import QuantReportResponse, get_precomputed_quant_score
from alphalens.llm.evidence import get_verified_evidence_claims

router = APIRouter(prefix="/api/reports", tags=["reports"])
limiter = Limiter(key_func=get_remote_address)

TICKER_REGEX = re.compile(r"^[A-Z0-9_\-&]+\.NS$")


class ChartCandle(BaseModel):
    """OHLCV candle for price charts."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class LiveQuoteResponse(BaseModel):
    """Real-time market snapshot from Yahoo Finance."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    last_price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    market_cap: float | None = None
    volume: int | None = None
    currency: str = "INR"
    is_live: bool = True
    history: list[ChartCandle] = []


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


@router.get("/{ticker}/live-quote", response_model=LiveQuoteResponse)
async def get_live_quote(
    ticker: str = Path(description="NSE Ticker symbol"),
    current_user: User = Depends(get_current_user),
) -> LiveQuoteResponse:
    """Fetch live market price snapshot from Yahoo Finance with fallback."""
    valid_ticker = validate_ticker(ticker)

    try:
        # Run blocking network call in threadpool
        def _fetch() -> LiveQuoteResponse:
            stock = yf.Ticker(valid_ticker)
            fast = stock.fast_info
            last_price = getattr(fast, "last_price", None)
            prev_close = getattr(fast, "previous_close", None)
            day_high = getattr(fast, "day_high", None)
            day_low = getattr(fast, "day_low", None)
            market_cap = getattr(fast, "market_cap", None)

            change_pct = None
            if last_price is not None and prev_close is not None and prev_close > 0:
                change_pct = round(((last_price - prev_close) / prev_close) * 100.0, 2)

            candles: list[ChartCandle] = []
            try:
                hist = stock.history(period="1mo", interval="1d")
                if not hist.empty:
                    for idx, row in hist.iterrows():
                        date_str = str(idx)[:10]
                        candles.append(
                            ChartCandle(
                                date=date_str,
                                open=round(float(row["Open"]), 2),
                                high=round(float(row["High"]), 2),
                                low=round(float(row["Low"]), 2),
                                close=round(float(row["Close"]), 2),
                                volume=int(row["Volume"]),
                            )
                        )
            except Exception:
                candles = []

            return LiveQuoteResponse(
                ticker=valid_ticker,
                last_price=round(float(last_price), 2) if last_price is not None else None,
                previous_close=round(float(prev_close), 2) if prev_close is not None else None,
                change_pct=change_pct,
                day_high=round(float(day_high), 2) if day_high is not None else None,
                day_low=round(float(day_low), 2) if day_low is not None else None,
                market_cap=round(float(market_cap), 2) if market_cap is not None else None,
                currency="INR",
                is_live=True,
                history=candles,
            )

        return await asyncio.to_thread(_fetch)
    except Exception:
        # Graceful fallback: return structure indicating live feed offline without failing page
        return LiveQuoteResponse(
            ticker=valid_ticker,
            is_live=False,
        )


@router.get("/{ticker}/econometrics")
async def get_econometrics_diagnostics(
    ticker: str = Path(description="NSE Ticker symbol"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Compute live econometric diagnostics: VaR/CVaR, higher-order moments, Kyle's Lambda, and HMM volatility regimes."""
    valid_ticker = validate_ticker(ticker)
    from dataclasses import asdict
    try:
        diagnostics = await asyncio.to_thread(compute_quantitative_diagnostics, valid_ticker)
        return asdict(diagnostics)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Econometric computation failed: {exc}",
        ) from exc


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
        from alphalens.config import get_settings

        settings = get_settings()
        # Check if LLM is configured
        if not settings.llm_api_key or not settings.llm_api_key.get_secret_value().strip():
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "stage": "disabled",
                        "message": "LLM evidence layer not enabled in this release",
                    }
                ),
            }
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "total_claims": 0,
                        "cached": False,
                        "ticker": valid_ticker,
                    }
                ),
            }
            return

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
