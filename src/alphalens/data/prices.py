"""Price data fetcher and quality analysis for NSE equities."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd
import structlog
import yfinance as yf
from pydantic import TypeAdapter, ValidationError

from alphalens.data.cache import cached
from alphalens.data.schemas import (
    DataQualityReport,
    PricePoint,
    PriceSeries,
    Ticker,
)

logger = structlog.get_logger("alphalens.data.prices")
_ticker_adapter = TypeAdapter(Ticker)


class PriceSource(Protocol):
    """Protocol defining interface for equity timeseries data providers."""

    def fetch(self, ticker: Ticker, start: date, end: date) -> PriceSeries:
        """Fetch historical price and corporate actions for an equity."""
        ...


def _clean_val(v: object) -> float | None:
    if v is None:
        return None
    if isinstance(v, (float, int, np.floating, np.integer)):
        if np.isnan(v):
            return None
        return float(v)
    return None


def _clean_int(v: object) -> int | None:
    if v is None:
        return None
    if isinstance(v, (float, int, np.floating, np.integer)):
        if np.isnan(v):
            return None
        return int(v)
    return None


class YFinancePriceSource:
    """Fetches historical price and corporate actions from Yahoo Finance."""

    def fetch(self, ticker: Ticker, start: date, end: date) -> PriceSeries:
        # Validate ticker format BEFORE attempting any network call
        try:
            validated_ticker = _ticker_adapter.validate_python(ticker)
        except ValidationError as exc:
            raise exc

        return self._fetch_cached(validated_ticker, start, end)

    @cached(namespace="prices")
    def _fetch_cached(self, ticker: Ticker, start: date, end: date) -> PriceSeries:
        validated_ticker = ticker

        # Call yfinance with threads disabled and explicit timeout
        yf_ticker = yf.Ticker(validated_ticker)
        df: pd.DataFrame = yf_ticker.history(
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            actions=True,
            timeout=10.0,
        )

        if df.empty or not isinstance(df, pd.DataFrame):
            # Return empty series with quality summary
            return PriceSeries(
                ticker=validated_ticker,
                start_date=start,
                end_date=end,
                points=[],
                quality=DataQualityReport(
                    extreme_moves=[],
                    stale_runs=[],
                    gaps=[],
                    adj_close_missing_ratio=0.0,
                    dropped_row_count=0,
                ),
            )

        # Standardize index timezone to IST (Asia/Kolkata)
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is not None:
                df.index = df.index.tz_convert("Asia/Kolkata")
            else:
                df.index = df.index.tz_localize("Asia/Kolkata")

        # Sort chronologically and drop duplicate dates (keeping first)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="first")]

        points: list[PricePoint] = []
        dropped_count = 0

        # Identify column names case-insensitively
        col_map = {str(c).lower().replace(" ", "_"): c for c in df.columns}
        open_col = col_map.get("open")
        high_col = col_map.get("high")
        low_col = col_map.get("low")
        close_col = col_map.get("close")
        adj_col = col_map.get("adj_close", col_map.get("adjclose", close_col))
        vol_col = col_map.get("volume")
        div_col = col_map.get("dividends", col_map.get("dividend"))
        split_col = col_map.get("stock_splits", col_map.get("splits", col_map.get("split")))

        for idx, row in df.iterrows():
            row_date: date = idx.date() if hasattr(idx, "date") else idx  # type: ignore[assignment]

            o = _clean_val(row[open_col]) if open_col else None
            h = _clean_val(row[high_col]) if high_col else None
            l_val = _clean_val(row[low_col]) if low_col else None
            c = _clean_val(row[close_col]) if close_col else None
            ac = _clean_val(row[adj_col]) if adj_col else None
            v = _clean_int(row[vol_col]) if vol_col else None
            d = _clean_val(row[div_col]) if div_col else None
            s = _clean_val(row[split_col]) if split_col else None

            # Drop row where all price fields are None
            if o is None and h is None and l_val is None and c is None and ac is None:
                dropped_count += 1
                continue

            # Row validity check: High must be >= Low, prices cannot be negative
            if (
                (h is not None and l_val is not None and h < l_val)
                or (h is not None and h < 0)
                or (l_val is not None and l_val < 0)
                or (c is not None and c < 0)
                or (ac is not None and ac < 0)
            ):
                dropped_count += 1
                logger.warning(
                    "dropped_corrupted_price_row ticker=%s date=%s",
                    validated_ticker,
                    row_date.isoformat(),
                )
                continue

            points.append(
                PricePoint(
                    date=row_date,
                    open=o,
                    high=h,
                    low=l_val,
                    close=c,
                    adj_close=ac,
                    volume=v,
                    dividend=d,
                    split_ratio=s,
                )
            )

        # Compute Quality flags
        extreme_moves: list[date] = []
        stale_runs: list[tuple[date, date]] = []

        # 1. Extreme moves: |daily return| > 20% on adj_close
        prev_adj: float | None = None
        for pt in points:
            if pt.adj_close is not None and prev_adj is not None and prev_adj > 0:
                ret = abs((pt.adj_close - prev_adj) / prev_adj)
                if ret > 0.20:
                    extreme_moves.append(pt.date)
            if pt.adj_close is not None:
                prev_adj = pt.adj_close

        # 2. Stale runs: 5+ consecutive days with identical close or zero volume
        current_run: list[PricePoint] = []
        for pt in points:
            is_stale_step = False
            if current_run:
                last_pt = current_run[-1]
                identical_close = (
                    pt.close is not None
                    and last_pt.close is not None
                    and abs(pt.close - last_pt.close) < 1e-6
                )
                zero_vol = pt.volume == 0
                if identical_close or zero_vol:
                    is_stale_step = True

            if is_stale_step:
                current_run.append(pt)
            else:
                if len(current_run) >= 5:
                    stale_runs.append((current_run[0].date, current_run[-1].date))
                current_run = [pt]

        if len(current_run) >= 5:
            stale_runs.append((current_run[0].date, current_run[-1].date))

        # 3. Missing adj_close ratio
        total_pts = len(points)
        missing_adj = sum(1 for p in points if p.adj_close is None)
        missing_ratio = (missing_adj / total_pts) if total_pts > 0 else 0.0

        quality = DataQualityReport(
            extreme_moves=extreme_moves,
            stale_runs=stale_runs,
            gaps=[],
            adj_close_missing_ratio=missing_ratio,
            dropped_row_count=dropped_count,
        )

        return PriceSeries(
            ticker=validated_ticker,
            start_date=start,
            end_date=end,
            points=points,
            quality=quality,
        )


_default_source: PriceSource = YFinancePriceSource()


def get_price_history(
    ticker: Ticker,
    start: date,
    end: date,
    source: PriceSource | None = None,
) -> PriceSeries:
    """Retrieve historical price and quality analysis for a given ticker."""
    active_source = source or _default_source
    return active_source.fetch(ticker, start, end)


def get_prices_bulk(
    tickers: Sequence[Ticker],
    start: date,
    end: date,
    source: PriceSource | None = None,
) -> tuple[dict[Ticker, PriceSeries], dict[Ticker, str]]:
    """Retrieve historical price series for multiple tickers sequentially.

    Continues execution if individual tickers fail and isolates errors.
    Returns: (successful_results_dict, failure_errors_dict)
    """
    results: dict[Ticker, PriceSeries] = {}
    failures: dict[Ticker, str] = {}
    active_source = source or _default_source

    for t in tickers:
        try:
            res = active_source.fetch(t, start, end)
            results[t] = res
        except Exception as exc:
            failures[t] = str(exc)
            logger.warning("bulk_price_fetch_failed", ticker=t, error=str(exc))

    return results, failures


def total_return_series(series: PriceSeries) -> list[tuple[date, float]]:
    """Extract chronological sequence of (date, adj_close) tuples for total return calculation."""
    return [(p.date, p.adj_close) for p in series.points if p.adj_close is not None]
