"""Nifty constituents universe catalog and reference loader.

LIMITATION / METHODOLOGICAL NOTE:
Using the current Nifty 50 constituents list across historical backtest windows
introduces survivorship bias (companies that underperformed and exited the index
historically are omitted, while current survivors are back-projected).
In Phase 6, point-in-time constituent lists per rebalance date should be used.
"""

import csv
import logging
from pathlib import Path

from pydantic import TypeAdapter

from alphalens.config import get_settings
from alphalens.data.schemas import Ticker, TickerInfo

logger = logging.getLogger("alphalens.data.universe")
_ticker_adapter = TypeAdapter(Ticker)

# Static catalog fallback for autocomplete and testing
NIFTY_100_CONSTITUENTS: list[TickerInfo] = [
    TickerInfo(symbol="RELIANCE.NS", name="Reliance Industries Ltd.", sector="Energy"),
    TickerInfo(
        symbol="TCS.NS", name="Tata Consultancy Services Ltd.", sector="Information Technology"
    ),
    TickerInfo(symbol="HDFCBANK.NS", name="HDFC Bank Ltd.", sector="Financial Services"),
    TickerInfo(symbol="ICICIBANK.NS", name="ICICI Bank Ltd.", sector="Financial Services"),
    TickerInfo(symbol="INFY.NS", name="Infosys Ltd.", sector="Information Technology"),
    TickerInfo(symbol="BHARTIARTL.NS", name="Bharti Airtel Ltd.", sector="Telecommunication"),
    TickerInfo(symbol="ITC.NS", name="ITC Ltd.", sector="Fast Moving Consumer Goods"),
    TickerInfo(symbol="SBIN.NS", name="State Bank of India", sector="Financial Services"),
    TickerInfo(symbol="LT.NS", name="Larsen & Toubro Ltd.", sector="Construction"),
    TickerInfo(
        symbol="HINDUNILVR.NS", name="Hindustan Unilever Ltd.", sector="Fast Moving Consumer Goods"
    ),
    TickerInfo(symbol="KOTAKBANK.NS", name="Kotak Mahindra Bank Ltd.", sector="Financial Services"),
    TickerInfo(symbol="AXISBANK.NS", name="Axis Bank Ltd.", sector="Financial Services"),
    TickerInfo(symbol="BAJFINANCE.NS", name="Bajaj Finance Ltd.", sector="Financial Services"),
    TickerInfo(
        symbol="MARUTI.NS", name="Maruti Suzuki India Ltd.", sector="Automobile and Auto Components"
    ),
    TickerInfo(
        symbol="TATAMOTORS.NS", name="Tata Motors Ltd.", sector="Automobile and Auto Components"
    ),
    TickerInfo(
        symbol="SUNPHARMA.NS", name="Sun Pharmaceutical Industries Ltd.", sector="Healthcare"
    ),
    TickerInfo(symbol="NTPC.NS", name="NTPC Ltd.", sector="Power"),
    TickerInfo(symbol="ONGC.NS", name="Oil & Natural Gas Corporation Ltd.", sector="Energy"),
    TickerInfo(symbol="TITAN.NS", name="Titan Company Ltd.", sector="Consumer Durables"),
    TickerInfo(symbol="ADANIENT.NS", name="Adani Enterprises Ltd.", sector="Metals & Mining"),
]


def load_nifty50_universe(reference_path: Path | None = None) -> list[TickerInfo]:
    """Load current Nifty 50 constituents from reference CSV.

    Source: data/reference/nifty50_constituents.csv (exported from niftyindices.com).
    Maps symbols to SYMBOL.NS, validates using Ticker type, and handles CSV headers.
    """
    settings = get_settings()
    target_path = reference_path or (settings.reference_dir / "nifty50_constituents.csv")

    if not target_path.exists():
        logger.warning(
            "nifty50_constituents_missing target_path=%s using_static_catalog",
            str(target_path),
        )
        return NIFTY_100_CONSTITUENTS

    constituents: list[TickerInfo] = []
    with target_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Keys can be 'Company Name', 'Industry', 'Symbol'
            norm_row = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}
            symbol_raw = norm_row.get("symbol")
            company_name = norm_row.get("company_name", symbol_raw or "")
            industry = norm_row.get("industry", "Unknown")

            if not symbol_raw:
                continue

            # Standardize symbol to SYMBOL.NS
            clean_sym = symbol_raw.upper()
            if not clean_sym.endswith(".NS"):
                clean_sym = f"{clean_sym}.NS"

            # Validate with Ticker TypeAdapter
            validated_symbol: Ticker = _ticker_adapter.validate_python(clean_sym)

            constituents.append(
                TickerInfo(
                    symbol=validated_symbol,
                    name=company_name,
                    sector=industry,
                )
            )

    return constituents


def search_universe(query: str, limit: int = 10) -> list[TickerInfo]:
    """Search constituents by ticker symbol or company name."""
    catalog = load_nifty50_universe()
    clean_q = query.strip().upper()
    if not clean_q:
        return catalog[:limit]

    matches: list[TickerInfo] = []
    for item in catalog:
        if clean_q in item.symbol.upper() or clean_q in item.name.upper():
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches
