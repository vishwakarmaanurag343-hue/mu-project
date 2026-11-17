"""Pure quantitative price factors computed point-in-time at month-end dates.

Strictly pure functions: no network calls, no DB calls, no LLM imports.
At date t, calculations strictly use data on or before t (NO LOOK-AHEAD).
Insufficient history -> None (never 0).
"""

import math
from datetime import date

import pandas as pd


def compute_month_ends(dates: pd.DatetimeIndex | list[date]) -> list[date]:
    """Identify month-end trading dates (the last available trading day of each month)."""
    s = pd.Series(dates).sort_values().drop_duplicates()
    s_dt = pd.to_datetime(s)
    # Group by (year, month) and take the maximum date in each group
    month_ends = s_dt.groupby([s_dt.dt.year, s_dt.dt.month]).max()
    return sorted([d.date() for d in month_ends])


def mom_12_1(prices: pd.Series, t: date) -> float | None:
    """Return from t-12m to t-1m.

    Uses prices up to date t.
    Specifically: P(t - 1m) / P(t - 12m) - 1.
    Requires at least 250 trading days prior to t and at least 21 days for the 1m exclusion.
    """
    history = prices.loc[:t].dropna()
    if len(history) < 250:
        return None

    # t - 1m corresponds to ~21 trading days prior to t
    # t - 12m corresponds to ~252 trading days prior to t
    p_1m = float(history.iloc[-21])
    p_12m = float(history.iloc[-252])

    if p_12m <= 0 or math.isnan(p_12m) or math.isnan(p_1m):
        return None

    return (p_1m / p_12m) - 1.0


def mom_6(prices: pd.Series, t: date) -> float | None:
    """Return from t-6m to t: P(t) / P(t - 6m) - 1.

    Requires at least 126 trading days prior to t.
    """
    history = prices.loc[:t].dropna()
    if len(history) < 126:
        return None

    p_t = float(history.iloc[-1])
    p_6m = float(history.iloc[-126])

    if p_6m <= 0 or math.isnan(p_6m) or math.isnan(p_t):
        return None

    return (p_t / p_6m) - 1.0


def rev_1m(prices: pd.Series, t: date) -> float | None:
    """Short-term reversal / return from t-1m to t: P(t) / P(t - 1m) - 1.

    Requires at least 21 trading days prior to t.
    """
    history = prices.loc[:t].dropna()
    if len(history) < 21:
        return None

    p_t = float(history.iloc[-1])
    p_1m = float(history.iloc[-21])

    if p_1m <= 0 or math.isnan(p_1m) or math.isnan(p_t):
        return None

    return (p_t / p_1m) - 1.0


def vol_6m(prices: pd.Series, t: date) -> float | None:
    """Annualized standard deviation of daily log returns over past 6 months (~126 trading days).

    Daily returns std * sqrt(252).
    Requires at least 126 daily returns (i.e. 127 price observations).
    """
    history = prices.loc[:t].dropna()
    if len(history) < 127:
        return None

    recent_6m = history.iloc[-127:]
    daily_returns = recent_6m.pct_change().dropna()
    if len(daily_returns) < 126:
        return None

    std_daily = float(daily_returns.std(ddof=1))
    if math.isnan(std_daily):
        return None

    return std_daily * math.sqrt(252.0)


def mdd_12m(prices: pd.Series, t: date) -> float | None:
    """Maximum drawdown over past 12 months (~252 trading days).

    (Peak - Trough) / Peak expressed as a non-positive or negative value (or min(P / Peak - 1)).
    Requires at least 252 trading days.
    """
    history = prices.loc[:t].dropna()
    if len(history) < 252:
        return None

    recent_12m = history.iloc[-252:]
    cum_max = recent_12m.cummax()
    drawdown = (recent_12m - cum_max) / cum_max
    min_dd = float(drawdown.min())

    if math.isnan(min_dd):
        return None

    return min_dd


def rel_strength_6m(stock_prices: pd.Series, benchmark_prices: pd.Series, t: date) -> float | None:
    """Stock 6m return minus benchmark 6m return.

    Uses strictly data on or before date t.
    """
    s_ret = mom_6(stock_prices, t)
    b_ret = mom_6(benchmark_prices, t)

    if s_ret is None or b_ret is None:
        return None

    return s_ret - b_ret


def compute_all_factors(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    t: date,
) -> dict[str, float | None]:
    """Compute all 6 price factors point-in-time at date t."""
    return {
        "mom_12_1": mom_12_1(stock_prices, t),
        "mom_6": mom_6(stock_prices, t),
        "rev_1m": rev_1m(stock_prices, t),
        "vol_6m": vol_6m(stock_prices, t),
        "mdd_12m": mdd_12m(stock_prices, t),
        "rel_strength_6m": rel_strength_6m(stock_prices, benchmark_prices, t),
    }
