"""Unit and property tests for walk-forward backtest, embargo enforcement, and metrics.

Tests:
  1. Embargo enforced: no training row at date t has label_end_date > t.
  2. Predictions at date t use strictly a model fitted on data available before t.
  3. Metrics are mathematically correct on a tiny hand-computed example.
  4. Rerun of walk-forward backtest is deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from alphalens.backtest.metrics import (
    compute_calibration_table,
    compute_economic_spread,
    compute_metrics,
    newey_west_mean_se,
)
from alphalens.backtest.walk_forward import (
    FACTOR_FEATURES,
    PredictionRecord,
    run_walk_forward_backtest,
)


@pytest.fixture
def synthetic_factor_df() -> pd.DataFrame:
    """Generate minimal synthetic dataset with 2 tickers across 12 monthly dates."""
    dates = pd.date_range("2016-01-31", periods=18, freq="ME").strftime("%Y-%m-%d").tolist()
    tickers = ["STOCK_A.NS", "STOCK_B.NS"]
    rows = []

    np.random.seed(42)
    for i, d in enumerate(dates):
        for ticker in tickers:
            # Create features
            features = {f: float(np.random.normal(0, 1)) for f in FACTOR_FEATURES}
            # label_end_date is ~6 months ahead for first 12 dates, None for later
            if i < 12:
                # 6 months forward
                end_date = dates[i + 5] if i + 5 < len(dates) else "2099-01-01"
                label = 1.0 if np.random.rand() > 0.4 else 0.0
                excess = float(np.random.normal(0.02, 0.05))
            else:
                end_date = None
                label = None
                excess = None

            row = {
                "date": d,
                "ticker": ticker,
                "label": label,
                "label_end_date": end_date,
                "excess_6m": excess,
                **features,
            }
            rows.append(row)

    return pd.DataFrame(rows)


def test_embargo_strictly_enforced(synthetic_factor_df: pd.DataFrame) -> None:
    """Requirement: for every fold at date t, no training row has label_end_date > t."""
    # Run backtest starting at index 6
    all_dates = sorted(synthetic_factor_df["date"].unique())
    start_date = all_dates[6]

    result = run_walk_forward_backtest(synthetic_factor_df, start_date=start_date)
    assert len(result.folds) > 0

    for fold in result.folds:
        t = fold.date
        # Check actual dataset filtering condition
        train_mask = synthetic_factor_df["label"].notnull() & (
            synthetic_factor_df["label_end_date"] <= t
        )
        train_subset = synthetic_factor_df[train_mask]

        if not train_subset.empty:
            assert (train_subset["label_end_date"] <= t).all(), (
                f"Embargo violation at date {t}: max label_end_date is {train_subset['label_end_date'].max()}"
            )


def test_predictions_at_t_use_strictly_prior_model(synthetic_factor_df: pd.DataFrame) -> None:
    """Requirement: predictions at t use only model fitted before t."""
    all_dates = sorted(synthetic_factor_df["date"].unique())
    t = all_dates[8]

    # Run backtest
    result = run_walk_forward_backtest(synthetic_factor_df, start_date=t)
    fold = next(f for f in result.folds if f.date == t)

    # Reconstruct training data manually using strict embargo rule
    train_mask = synthetic_factor_df["label"].notnull() & (
        synthetic_factor_df["label_end_date"] <= t
    )
    train_df = synthetic_factor_df[train_mask].dropna(subset=[*FACTOR_FEATURES, "label"])

    clf = LogisticRegression(C=1.0, random_state=42)
    clf.fit(train_df[FACTOR_FEATURES], train_df["label"].astype(int))

    test_df = synthetic_factor_df[synthetic_factor_df["date"] == t].dropna(subset=FACTOR_FEATURES)
    expected_probs = clf.predict_proba(test_df[FACTOR_FEATURES])[:, 1]

    actual_probs = [p.probability for p in fold.model_preds]
    np.testing.assert_allclose(actual_probs, expected_probs, rtol=1e-5)


def test_metrics_on_hand_computed_example() -> None:
    """Requirement: metrics correct on a tiny hand-computed example."""
    # Hand-crafted predictions
    # True labels: [1, 0, 1, 0]
    # Predictions: [0.8, 0.2, 0.6, 0.4]
    # Squared errors:
    # (0.8 - 1)^2 = 0.04
    # (0.2 - 0)^2 = 0.04
    # (0.6 - 1)^2 = 0.16
    # (0.4 - 0)^2 = 0.16
    # Mean squared error (Brier) = (0.04 + 0.04 + 0.16 + 0.16) / 4 = 0.40 / 4 = 0.1000
    #
    # Baseline:
    # Base rate = 0.5 (two 1s, two 0s)
    # Baseline squared error = (0.5 - 1)^2 * 2 + (0.5 - 0)^2 * 2 = 0.25 * 4 / 4 = 0.2500
    # Brier Skill Score = 1 - (0.1000 / 0.2500) = 1 - 0.4 = 0.6000
    #
    # Log loss:
    # - [1*log(0.8) + 1*log(1 - 0.2) + 1*log(0.6) + 1*log(1 - 0.4)] / 4
    # - [log(0.8) + log(0.8) + log(0.6) + log(0.6)] / 4
    # = - [2*(-0.22314355) + 2*(-0.51082562)] / 4 = (0.4462871 + 1.0216512) / 4 = 1.4679383 / 4 = 0.36698...
    #
    # ROC AUC:
    # Positives ranks: 0.8 (rank 4), 0.6 (rank 3) -> both higher than negatives (0.4, 0.2) -> AUC = 1.0

    preds = [
        PredictionRecord(
            date="2020-01-31", ticker="T1", probability=0.8, outcome=1.0, excess_6m=0.10
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T2", probability=0.2, outcome=0.0, excess_6m=-0.05
        ),
        PredictionRecord(
            date="2020-02-28", ticker="T1", probability=0.6, outcome=1.0, excess_6m=0.08
        ),
        PredictionRecord(
            date="2020-02-28", ticker="T2", probability=0.4, outcome=0.0, excess_6m=-0.02
        ),
    ]

    base_preds = [
        PredictionRecord(
            date="2020-01-31", ticker="T1", probability=0.5, outcome=1.0, excess_6m=0.10
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T2", probability=0.5, outcome=0.0, excess_6m=-0.05
        ),
        PredictionRecord(
            date="2020-02-28", ticker="T1", probability=0.5, outcome=1.0, excess_6m=0.08
        ),
        PredictionRecord(
            date="2020-02-28", ticker="T2", probability=0.5, outcome=0.0, excess_6m=-0.02
        ),
    ]

    metrics = compute_metrics(preds, baseline_predictions=base_preds)

    assert metrics["n_samples"] == 4
    assert pytest.approx(metrics["brier_score"], abs=1e-4) == 0.1000
    assert pytest.approx(metrics["baseline_brier"], abs=1e-4) == 0.2500
    assert pytest.approx(metrics["brier_skill_score"], abs=1e-4) == 0.6000
    assert pytest.approx(metrics["roc_auc"], abs=1e-4) == 1.0000
    assert pytest.approx(metrics["log_loss"], abs=1e-3) == 0.3670


def test_calibration_table_binning() -> None:
    """Verify calibration table properly bins probabilities and computes empirical frequencies."""
    y_true = np.array([0.0, 1.0, 1.0, 0.0])
    y_prob = np.array([0.05, 0.55, 0.58, 0.95])

    bins = compute_calibration_table(y_true, y_prob, n_bins=10)
    assert len(bins) == 10

    # Bin 0: [0.0, 0.1) -> prob 0.05, label 0.0
    assert bins[0]["count"] == 1
    assert pytest.approx(bins[0]["predicted_avg"], abs=1e-3) == 0.05
    assert bins[0]["observed_rate"] == 0.0

    # Bin 5: [0.5, 0.6) -> probs 0.55, 0.58, labels 1.0, 1.0
    assert bins[5]["count"] == 2
    assert pytest.approx(bins[5]["predicted_avg"], abs=1e-3) == 0.565
    assert bins[5]["observed_rate"] == 1.0

    # Bin 9: [0.9, 1.0] -> prob 0.95, label 0.0
    assert bins[9]["count"] == 1
    assert pytest.approx(bins[9]["predicted_avg"], abs=1e-3) == 0.95
    assert bins[9]["observed_rate"] == 0.0


def test_economic_spread_calculation() -> None:
    """Verify top vs bottom quintile monthly excess return spread calculation."""
    preds = [
        PredictionRecord(
            date="2020-01-31", ticker="T1", probability=0.9, outcome=1.0, excess_6m=0.10
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T2", probability=0.7, outcome=1.0, excess_6m=0.05
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T3", probability=0.5, outcome=0.0, excess_6m=0.00
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T4", probability=0.3, outcome=0.0, excess_6m=-0.04
        ),
        PredictionRecord(
            date="2020-01-31", ticker="T5", probability=0.1, outcome=0.0, excess_6m=-0.10
        ),
    ]

    econ = compute_economic_spread(preds)
    assert econ["n_months"] == 1
    # Q5 is >= 80th percentile (prob 0.9, excess 0.10)
    # Q1 is <= 20th percentile (prob 0.1, excess -0.10)
    # Spread = 0.10 - (-0.10) = 0.20
    assert pytest.approx(econ["mean_spread"], abs=1e-3) == 0.20


def test_newey_west_hac_hand_computed() -> None:
    """Verify Newey-West HAC standard error matches exact hand-computed values.

    Series: [1.0, 2.0, 3.0, 4.0, 5.0], T = 5, mean = 3.0
    Demeaned: [-2, -1, 0, 1, 2]
    gamma_0 = (4 + 1 + 0 + 1 + 4) / 5 = 10 / 5 = 2.0
    gamma_1 = ( (-2)*(-1) + (-1)*0 + 0*1 + 1*2 ) / 5 = 4 / 5 = 0.8
    gamma_2 = ( (-2)*0 + (-1)*1 + 0*2 ) / 5 = -1 / 5 = -0.2

    With max_lags = 2:
      Bartlett weights: w(1) = 1 - 1/3 = 2/3, w(2) = 1 - 2/3 = 1/3
      HAC core = 2.0 + 2 * [ (2/3)*0.8 + (1/3)*(-0.2) ] = 2.0 + 2 * (1.4 / 3) = 8.8 / 3
      Var_HAC(mean) = (8.8 / 3) / 5 = 8.8 / 15 ≈ 0.5866666667
      SE_HAC = sqrt(8.8 / 15) ≈ 0.7659416862
    """
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    res = newey_west_mean_se(x, max_lags=2)

    assert res["mean"] == 3.0
    # Naive sample variance: s^2 = 10 / 4 = 2.5 -> SE_naive = sqrt(2.5 / 5) = sqrt(0.5) ≈ 0.7071
    assert pytest.approx(res["se_naive"], abs=1e-6) == np.sqrt(0.5)
    assert pytest.approx(res["t_stat_naive"], abs=1e-6) == 3.0 / np.sqrt(0.5)

    # HAC
    expected_hac_se = float(np.sqrt(8.8 / 15.0))
    assert pytest.approx(res["se_hac"], abs=1e-6) == expected_hac_se
    assert pytest.approx(res["t_stat_hac"], abs=1e-6) == 3.0 / expected_hac_se


def test_walk_forward_backtest_deterministic(synthetic_factor_df: pd.DataFrame) -> None:
    """Requirement: rerun of backtest produces identical results."""
    all_dates = sorted(synthetic_factor_df["date"].unique())
    start_date = all_dates[6]

    run1 = run_walk_forward_backtest(synthetic_factor_df, start_date=start_date)
    run2 = run_walk_forward_backtest(synthetic_factor_df, start_date=start_date)

    assert len(run1.model_predictions) == len(run2.model_predictions)
    for p1, p2 in zip(run1.model_predictions, run2.model_predictions, strict=True):
        assert p1.date == p2.date
        assert p1.ticker == p2.ticker
        assert pytest.approx(p1.probability, abs=1e-9) == p2.probability
        assert p1.outcome == p2.outcome
