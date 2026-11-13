"""Ticker universe autocomplete endpoint."""

from fastapi import APIRouter, Query

from alphalens.data.schemas import TickerInfo
from alphalens.data.universe import search_universe

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


@router.get("", response_model=list[TickerInfo])
async def autocomplete_tickers(
    q: str = Query(default="", max_length=50, description="Search query by symbol or company name"),
) -> list[TickerInfo]:
    """Autocomplete over Nifty 100 historical constituents, returning at most 10 results."""
    return search_universe(query=q, limit=10)
