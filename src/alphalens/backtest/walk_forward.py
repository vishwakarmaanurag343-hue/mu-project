"""Walk-forward backtest engine with strict embargo enforcement.

ADR-001: P(stock 6-month TR > Nifty 50 TR).
Point-in-time cross-sectional factors with embargo on overlapping forward return windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from sklearn.linear_model import LogisticRegression

FACTOR_FEATURES: list[str] = [
    "mom_12_1_z",
    "mom_6_z",
    "rev_1m_z",
    "vol_6m_z",
    "mdd_12m_z",
    "rel_strength_6m_z",
]

MOMENTUM_FEATURE: list[str] = ["mom_12_1_z"]


@dataclass(frozen=True)
class PredictionRecord:
    """Out-of-sample prediction record at rebalance date t."""

    date: str
    ticker: str
    probability: float
    outcome: float | None  # 1.0, 0.0, or None (if unlabelled/future)
    excess_6m: float | None


@dataclass
class WalkForwardFoldResult:
    """Diagnostic details for a single walk-forward rebalance date t."""

    date: str
    train_size: int
    train_dates: tuple[str, str]
    dropped_train_rows: int
    dropped_test_rows: int
    base_rate: float
    model_preds: list[PredictionRecord]
    base_preds: list[PredictionRecord]
    mom_preds: list[PredictionRecord]


@dataclass
class WalkForwardResult:
    """Aggregate result of walk-forward validation across all dates."""

    folds: list[WalkForwardFoldResult]
    model_predictions: list[PredictionRecord] = field(default_factory=list)
    base_predictions: list[PredictionRecord] = field(default_factory=list)
    mom_predictions: list[PredictionRecord] = field(default_factory=list)
    total_dropped_train_rows: int = 0
    total_dropped_test_rows: int = 0


def run_walk_forward_backtest(
    df: pd.DataFrame,
    start_date: str = "2017-01-01",
    features: list[str] | None = None,
) -> WalkForwardResult:
    """Run monthly walk-forward backtest with strict embargo.

    For each month-end date t from start_date onward:
      - Training set: rows with label not None AND label_end_date <= t.
        (EMBARGO: strictly no future or overlapping labels included).
      - Test set: rows where date == t.
      - LogisticRegression (L2 regularization, C=1.0, random_state=42).
      - Baselines at t:
          (a) Base-rate baseline: mean label of training set (trailing out-of-sample).
          (b) Momentum-only baseline: LogisticRegression on mom_12_1_z.
    """
    if features is None:
        features = FACTOR_FEATURES

    all_dates = sorted(df["date"].unique())
    test_dates = [d for d in all_dates if d >= start_date]

    folds: list[WalkForwardFoldResult] = []
    all_model_preds: list[PredictionRecord] = []
    all_base_preds: list[PredictionRecord] = []
    all_mom_preds: list[PredictionRecord] = []

    total_dropped_train = 0
    total_dropped_test = 0

    for t in test_dates:
        # EMBARGO: training rows must have resolved labels whose evaluation window
        # closed on or before date t.
        train_mask = df["label"].notnull() & (df["label_end_date"] <= t)
        train_df = df[train_mask]

        if train_df.empty:
            continue

        test_mask = df["date"] == t
        test_df = df[test_mask]

        if test_df.empty:
            continue

        # Baseline 1: Trailing base rate
        base_rate = float(train_df["label"].mean())
        fold_base_preds: list[PredictionRecord] = []
        for row in test_df.itertuples():
            outcome_val = None if pd.isna(row.label) else float(row.label)
            excess_val = None if pd.isna(row.excess_6m) else float(row.excess_6m)
            fold_base_preds.append(
                PredictionRecord(
                    date=str(row.date),
                    ticker=str(row.ticker),
                    probability=base_rate,
                    outcome=outcome_val,
                    excess_6m=excess_val,
                )
            )

        # Baseline 2: Momentum-only logistic regression
        train_mom = train_df.dropna(subset=[*MOMENTUM_FEATURE, "label"])
        test_mom = test_df.dropna(subset=MOMENTUM_FEATURE)
        fold_mom_preds: list[PredictionRecord] = []
        if len(train_mom["label"].unique()) > 1 and not test_mom.empty:
            clf_mom = LogisticRegression(C=1.0, random_state=42)
            clf_mom.fit(train_mom[MOMENTUM_FEATURE], train_mom["label"].astype(int))
            probs_mom = clf_mom.predict_proba(test_mom[MOMENTUM_FEATURE])[:, 1]
            for row, p in zip(test_mom.itertuples(), probs_mom, strict=True):
                outcome_val = None if pd.isna(row.label) else float(row.label)
                excess_val = None if pd.isna(row.excess_6m) else float(row.excess_6m)
                fold_mom_preds.append(
                    PredictionRecord(
                        date=str(row.date),
                        ticker=str(row.ticker),
                        probability=float(p),
                        outcome=outcome_val,
                        excess_6m=excess_val,
                    )
                )

        # Multi-factor model
        train_clean = train_df.dropna(subset=[*features, "label"])
        test_clean = test_df.dropna(subset=features)

        dropped_train = len(train_df) - len(train_clean)
        dropped_test = len(test_df) - len(test_clean)
        total_dropped_train += dropped_train
        total_dropped_test += dropped_test

        fold_model_preds: list[PredictionRecord] = []
        if len(train_clean["label"].unique()) > 1 and not test_clean.empty:
            clf = LogisticRegression(C=1.0, random_state=42)
            clf.fit(train_clean[features], train_clean["label"].astype(int))
            probs = clf.predict_proba(test_clean[features])[:, 1]
            for row, p in zip(test_clean.itertuples(), probs, strict=True):
                outcome_val = None if pd.isna(row.label) else float(row.label)
                excess_val = None if pd.isna(row.excess_6m) else float(row.excess_6m)
                fold_model_preds.append(
                    PredictionRecord(
                        date=str(row.date),
                        ticker=str(row.ticker),
                        probability=float(p),
                        outcome=outcome_val,
                        excess_6m=excess_val,
                    )
                )

        train_min_date = str(train_clean["date"].min())
        train_max_date = str(train_clean["date"].max())

        fold_res = WalkForwardFoldResult(
            date=t,
            train_size=len(train_clean),
            train_dates=(train_min_date, train_max_date),
            dropped_train_rows=dropped_train,
            dropped_test_rows=dropped_test,
            base_rate=base_rate,
            model_preds=fold_model_preds,
            base_preds=fold_base_preds,
            mom_preds=fold_mom_preds,
        )
        folds.append(fold_res)
        all_model_preds.extend(fold_model_preds)
        all_base_preds.extend(fold_base_preds)
        all_mom_preds.extend(fold_mom_preds)

    return WalkForwardResult(
        folds=folds,
        model_predictions=all_model_preds,
        base_predictions=all_base_preds,
        mom_predictions=all_mom_preds,
        total_dropped_train_rows=total_dropped_train,
        total_dropped_test_rows=total_dropped_test,
    )
