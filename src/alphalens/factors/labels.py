"""Prediction target labels and forward total return calculations.

Prediction Target (ADR-001):
excess_6m = stock TR(t -> t+6m) - benchmark TR(t -> t+6m)
label = 1 if excess_6m > 0 else 0
label_end_date = t + 6 months trading day (~126 trading days ahead).
If future data is not available -> label and excess_6m are None.
"""

import math
from datetime import date

import pandas as pd

FORWARD_HORIZON_TRADING_DAYS = 126  # ~6 months of trading days


def forward_total_return(
    prices: pd.Series, t: date, horizon_days: int = FORWARD_HORIZON_TRADING_DAYS
) -> tuple[float | None, date | None]:
    """Compute forward return P(t + horizon) / P(t) - 1 and return forward date."""
    future = prices.loc[t:].dropna()
    if len(future) <= horizon_days:
        return None, None

    p_t = float(future.iloc[0])
    p_future = float(future.iloc[horizon_days])
    target_date = future.index[horizon_days]
    if hasattr(target_date, "date"):
        target_date = target_date.date()

    if p_t <= 0 or math.isnan(p_t) or math.isnan(p_future):
        return None, None

    fwd_ret = (p_future / p_t) - 1.0
    return fwd_ret, target_date


def compute_label(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    t: date,
    horizon_days: int = FORWARD_HORIZON_TRADING_DAYS,
) -> tuple[float | None, int | None, date | None]:
    """Compute (excess_6m, label, label_end_date) at date t.

    excess_6m = stock TR(t -> t+6m) - benchmark TR(t -> t+6m)
    label = 1 if excess_6m > 0 else 0
    Returns: (excess_6m, label, label_end_date)
    """
    s_ret, s_target_date = forward_total_return(stock_prices, t, horizon_days)
    b_ret, _b_target_date = forward_total_return(benchmark_prices, t, horizon_days)

    if s_ret is None or b_ret is None or s_target_date is None:
        return None, None, None

    excess = s_ret - b_ret
    lbl = 1 if excess > 0.0 else 0
    return excess, lbl, s_target_date
