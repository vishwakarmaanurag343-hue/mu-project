"""Unit tests and Hypothesis property tests for point-in-time factors, labels, and dataset builder."""

import math
from datetime import date

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alphalens.factors.dataset import build_factor_dataset
from alphalens.factors.labels import compute_label
from alphalens.factors.price_factors import (
    compute_all_factors,
    mdd_12m,
    mom_6,
    mom_12_1,
    rev_1m,
    vol_6m,
)


def create_synthetic_daily_series(
    start: date,
    num_days: int,
    initial_price: float = 100.0,
    daily_growth: float = 0.001,
) -> pd.Series:
    """Generate deterministic synthetic price series with consecutive business days."""
    dates = pd.bdate_range(start=start, periods=num_days)
    prices = [initial_price * ((1.0 + daily_growth) ** i) for i in range(num_days)]
    s = pd.Series(prices, index=[d.date() for d in dates])
    return s


def test_missing_history_returns_none() -> None:
    """Insufficient history returns None, never 0."""
    start = date(2020, 1, 1)
    # Only 50 days of data
    short_prices = create_synthetic_daily_series(start, 50)
    t = short_prices.index[-1]

    # Needs 250 days
    assert mom_12_1(short_prices, t) is None
    # Needs 126 days
    assert mom_6(short_prices, t) is None
    # Needs 127 days
    assert vol_6m(short_prices, t) is None
    # Needs 252 days
    assert mdd_12m(short_prices, t) is None


def test_hand_computed_factors() -> None:
    """Known synthetic series give exact hand-computed factor values."""
    start = date(2020, 1, 1)
    prices_list = [100.0] * 300
    # Let price at day 299 be 110.0, day 278 (21 days back) be 100.0
    # day 173 (126 days back) be 100.0, day 47 (252 days back) be 100.0
    dates = pd.bdate_range(start=start, periods=300)
    s = pd.Series(prices_list, index=[d.date() for d in dates])
    t = s.index[-1]

    # With constant 100.0:
    # returns are 0.0, volatility is 0.0, mdd is 0.0
    assert mom_6(s, t) == pytest.approx(0.0)
    assert rev_1m(s, t) == pytest.approx(0.0)
    assert vol_6m(s, t) == pytest.approx(0.0)
    assert mdd_12m(s, t) == pytest.approx(0.0)
    assert mom_12_1(s, t) == pytest.approx(0.0)

    # Modify last day to 110.0 -> rev_1m = 110 / 100 - 1 = +0.10
    s.iloc[-1] = 110.0
    assert rev_1m(s, t) == pytest.approx(0.10)
    assert mom_6(s, t) == pytest.approx(0.10)

    # Check Drawdown: peak is 110.0, drop to 99.0
    s_dd = s.copy()
    s_dd.iloc[-1] = 99.0  # Peak before was 100.0, now 99 -> -0.01 drawdown
    assert mdd_12m(s_dd, t) == pytest.approx(-0.01)


def test_label_computation_future_horizon() -> None:
    """Labels use exactly t -> t+6m (~126 trading days); None when future missing."""
    start = date(2020, 1, 1)
    # 200 trading days total
    stock_prices = create_synthetic_daily_series(
        start, 200, initial_price=100.0, daily_growth=0.002
    )
    bench_prices = create_synthetic_daily_series(
        start, 200, initial_price=100.0, daily_growth=0.001
    )

    # At day 0 (index 0): 126 trading days in future exists!
    t0 = stock_prices.index[0]
    excess, label, label_end = compute_label(stock_prices, bench_prices, t0)
    assert excess is not None
    assert excess > 0.0  # stock grew at 0.002 vs bench at 0.001
    assert label == 1
    assert label_end == stock_prices.index[126]

    # At day 150 (index 150): only 50 future days exist (< 126) -> None!
    t_late = stock_prices.index[150]
    excess_late, label_late, label_end_late = compute_label(stock_prices, bench_prices, t_late)
    assert excess_late is None
    assert label_late is None
    assert label_end_late is None


def test_dataset_builder_pipeline() -> None:
    """build_factor_dataset correctly structures rows, computes cross-sectional z-scores, and winsorises."""
    start = date(2020, 1, 1)
    s1 = create_synthetic_daily_series(start, 350, initial_price=100.0, daily_growth=0.001)
    s2 = create_synthetic_daily_series(start, 350, initial_price=200.0, daily_growth=0.002)
    bench = create_synthetic_daily_series(start, 350, initial_price=5000.0, daily_growth=0.0015)

    prices_df = pd.DataFrame({"STOCK1.NS": s1, "STOCK2.NS": s2})
    dataset_df = build_factor_dataset(prices_df, bench)

    assert not dataset_df.empty
    assert "mom_6" in dataset_df.columns
    assert "mom_6_z" in dataset_df.columns
    assert "label" in dataset_df.columns

    # Verify z-scores are bounded within [-3.0, 3.0]
    z_cols = [c for c in dataset_df.columns if c.endswith("_z")]
    for col in z_cols:
        vals = dataset_df[col].dropna()
        if len(vals) > 0:
            assert (vals >= -3.0).all()
            assert (vals <= 3.0).all()


@settings(max_examples=20, deadline=None)
@given(
    future_multiplier=st.floats(min_value=0.1, max_value=10.0),
    future_offset_days=st.integers(min_value=1, max_value=50),
)
def test_no_look_ahead_property(future_multiplier: float, future_offset_days: int) -> None:
    """HYPOTHESIS PROPERTY: Modifying prices after date t strictly does NOT affect factors at t."""
    start = date(2020, 1, 1)
    num_days = 300
    base_series = create_synthetic_daily_series(start, num_days, initial_price=100.0)
    bench_series = create_synthetic_daily_series(start, num_days, initial_price=1000.0)

    # Evaluation date t at index 260
    t_idx = 260
    t = base_series.index[t_idx]

    # Baseline factor calculations
    base_factors = compute_all_factors(base_series, bench_series, t)

    # Mutate future price at (t_idx + future_offset_days)
    mutated_series = base_series.copy()
    future_idx = min(num_days - 1, t_idx + future_offset_days)
    mutated_series.iloc[future_idx] *= future_multiplier

    # Factors at t after future mutation
    mutated_factors = compute_all_factors(mutated_series, bench_series, t)

    # Assert EVERY factor is 100% identical
    for factor_name, base_val in base_factors.items():
        mutated_val = mutated_factors[factor_name]
        if base_val is None:
            assert mutated_val is None
        else:
            assert math.isclose(base_val, mutated_val, rel_tol=1e-9), (
                f"Leakage detected in {factor_name}!"
            )
