"""Statistical evaluation, calibration metrics, and economic check.

Computes:
  - Brier score
  - Brier Skill Score (BSS) vs trailing base-rate baseline
  - Log loss
  - ROC AUC
  - Calibration curve (10 bins)
  - Economic check: average excess_6m of top-quintile vs bottom-quintile predictions per month (spread, mean, t-stat)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from alphalens.backtest.walk_forward import PredictionRecord


def compute_calibration_table(
    y_true: np.ndarray[Any, np.dtype[np.float64]],
    y_prob: np.ndarray[Any, np.dtype[np.float64]],
    n_bins: int = 10,
) -> list[dict[str, Any]]:
    """Compute calibration table across 10 equal-width bins in [0, 1].

    Bins: [0.0, 0.1), [0.1, 0.2), ..., [0.9, 1.0].
    """
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: list[dict[str, Any]] = []

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= low) & (y_prob <= high)
        else:
            mask = (y_prob >= low) & (y_prob < high)

        count = int(np.sum(mask))
        bin_center = round(float((low + high) / 2.0), 2)
        if count > 0:
            pred_avg = round(float(np.mean(y_prob[mask])), 4)
            obs_rate = round(float(np.mean(y_true[mask])), 4)
        else:
            pred_avg = bin_center
            obs_rate = 0.0

        bins.append(
            {
                "bin_center": bin_center,
                "predicted_avg": pred_avg,
                "observed_rate": obs_rate,
                "count": count,
            }
        )

    return bins


def newey_west_mean_se(
    x: np.ndarray[Any, np.dtype[np.float64]] | list[float], max_lags: int = 5
) -> dict[str, float]:
    """Compute mean, naive standard error, and Newey-West HAC standard error with Bartlett kernel.

    For overlapping returns (e.g., 6-month returns sampled monthly -> lag 5):
      gamma_0 = (1/T) sum_{t=1}^T (x_t - mean)^2
      gamma_l = (1/T) sum_{t=l+1}^T (x_t - mean)(x_{t-l} - mean)
      Var_HAC(mean) = (1/T) [ gamma_0 + 2 * sum_{l=1}^L (1 - l/(L+1)) * gamma_l ]
      SE_HAC = sqrt(Var_HAC(mean))
    """
    arr = np.asarray(x, dtype=np.float64)
    t_len = len(arr)
    if t_len == 0:
        return {
            "mean": 0.0,
            "se_naive": 0.0,
            "t_stat_naive": 0.0,
            "p_value_naive": 1.0,
            "se_hac": 0.0,
            "t_stat_hac": 0.0,
            "p_value_hac": 1.0,
        }

    mean_val = float(np.mean(arr))
    if t_len == 1:
        return {
            "mean": mean_val,
            "se_naive": 0.0,
            "t_stat_naive": 0.0,
            "p_value_naive": 1.0,
            "se_hac": 0.0,
            "t_stat_hac": 0.0,
            "p_value_hac": 1.0,
        }

    # Naive sample variance and standard error (ddof=1)
    s2 = float(np.var(arr, ddof=1))
    se_naive = float(np.sqrt(s2 / t_len)) if s2 > 0.0 else 0.0
    if se_naive > 0.0:
        t_naive = mean_val / se_naive
        p_naive = float(2.0 * (1.0 - stats.t.cdf(abs(t_naive), df=t_len - 1)))
    else:
        t_naive = 0.0
        p_naive = 1.0

    # Newey-West HAC with Bartlett kernel
    demeaned = arr - mean_val
    gamma_0 = float(np.dot(demeaned, demeaned) / t_len)
    hac_var_core = gamma_0

    lags = min(max_lags, t_len - 1)
    for lag in range(1, lags + 1):
        weight = 1.0 - (lag / (lags + 1.0))
        gamma_lag = float(np.dot(demeaned[lag:], demeaned[:-lag]) / t_len)
        hac_var_core += 2.0 * weight * gamma_lag

    var_mean_hac = max(0.0, hac_var_core / t_len)
    se_hac = float(np.sqrt(var_mean_hac))

    if se_hac > 0.0:
        t_hac = mean_val / se_hac
        p_hac = float(2.0 * (1.0 - stats.t.cdf(abs(t_hac), df=t_len - 1)))
    else:
        t_hac = 0.0
        p_hac = 1.0

    return {
        "mean": mean_val,
        "se_naive": se_naive,
        "t_stat_naive": t_naive,
        "p_value_naive": p_naive,
        "se_hac": se_hac,
        "t_stat_hac": t_hac,
        "p_value_hac": p_hac,
    }


def compute_economic_spread(
    predictions: list[PredictionRecord],
    max_lags: int = 5,
) -> dict[str, Any]:
    """Compute top-quintile vs bottom-quintile 6-month excess return spread per month.

    Groups resolved predictions by rebalance date.
    Top quintile (Q5): predictions >= 80th percentile probability at date t.
    Bottom quintile (Q1): predictions <= 20th percentile probability at date t.
    Monthly spread = mean(excess_6m for Q5) - mean(excess_6m for Q1).
    Evaluates both naive and Newey-West HAC (lag 5) t-statistics and p-values.
    """
    resolved = [p for p in predictions if p.outcome is not None and p.excess_6m is not None]
    if not resolved:
        return {
            "monthly_spreads": [],
            "mean_spread": 0.0,
            "std_spread": 0.0,
            "se_naive": 0.0,
            "t_stat": 0.0,
            "p_value": 1.0,
            "t_stat_naive": 0.0,
            "p_value_naive": 1.0,
            "se_hac": 0.0,
            "t_stat_hac": 0.0,
            "p_value_hac": 1.0,
            "n_months": 0,
            "hac_lags": max_lags,
        }

    df = pd.DataFrame(
        [
            {"date": p.date, "ticker": p.ticker, "prob": p.probability, "excess_6m": p.excess_6m}
            for p in resolved
        ]
    )

    monthly_spreads: list[dict[str, Any]] = []
    spread_values: list[float] = []

    for d, group in df.groupby("date"):
        if len(group) < 5:
            continue
        q_high = float(group["prob"].quantile(0.8))
        q_low = float(group["prob"].quantile(0.2))

        top_ret = float(group[group["prob"] >= q_high]["excess_6m"].mean())
        bot_ret = float(group[group["prob"] <= q_low]["excess_6m"].mean())
        spread = top_ret - bot_ret

        monthly_spreads.append(
            {
                "date": str(d),
                "top_quintile_excess": round(top_ret, 4),
                "bottom_quintile_excess": round(bot_ret, 4),
                "spread": round(spread, 4),
            }
        )
        spread_values.append(spread)

    if not spread_values:
        return {
            "monthly_spreads": [],
            "mean_spread": 0.0,
            "std_spread": 0.0,
            "se_naive": 0.0,
            "t_stat": 0.0,
            "p_value": 1.0,
            "t_stat_naive": 0.0,
            "p_value_naive": 1.0,
            "se_hac": 0.0,
            "t_stat_hac": 0.0,
            "p_value_hac": 1.0,
            "n_months": 0,
            "hac_lags": max_lags,
        }

    std_spread = float(np.std(spread_values, ddof=1)) if len(spread_values) > 1 else 0.0
    hac_res = newey_west_mean_se(spread_values, max_lags=max_lags)

    return {
        "monthly_spreads": monthly_spreads,
        "mean_spread": round(hac_res["mean"], 4),
        "std_spread": round(std_spread, 4),
        "se_naive": round(hac_res["se_naive"], 4),
        "t_stat": round(hac_res["t_stat_hac"], 4),  # Primary reported t-stat is HAC
        "p_value": round(hac_res["p_value_hac"], 4),
        "t_stat_naive": round(hac_res["t_stat_naive"], 4),
        "p_value_naive": round(hac_res["p_value_naive"], 4),
        "se_hac": round(hac_res["se_hac"], 4),
        "t_stat_hac": round(hac_res["t_stat_hac"], 4),
        "p_value_hac": round(hac_res["p_value_hac"], 4),
        "n_months": len(spread_values),
        "hac_lags": max_lags,
    }


def compute_metrics(
    predictions: list[PredictionRecord],
    baseline_predictions: list[PredictionRecord] | None = None,
    is_base_rate_baseline: bool = False,
) -> dict[str, Any]:
    """Compute complete metric suite on out-of-sample predictions with resolved labels.

    Metrics:
      - brier_score
      - brier_skill_score (BSS vs baseline)
      - log_loss
      - roc_auc (or "N/A" for base-rate baseline)
      - calibration_table
      - economic_check (top vs bottom quintile spread, mean, t-stat)
    """
    resolved = [p for p in predictions if p.outcome is not None]
    if not resolved:
        return {
            "n_samples": 0,
            "brier_score": 0.0,
            "brier_skill_score": 0.0,
            "log_loss": 0.0,
            "roc_auc": "N/A" if is_base_rate_baseline else 0.5,
            "calibration_table": [],
            "economic": compute_economic_spread([]),
        }

    y_true = np.array([p.outcome for p in resolved], dtype=np.float64)
    y_prob = np.array([p.probability for p in resolved], dtype=np.float64)

    # Clip probabilities to avoid log(0)
    y_prob_clipped = np.clip(y_prob, 1e-15, 1.0 - 1e-15)

    brier = float(brier_score_loss(y_true, y_prob))
    ll = float(log_loss(y_true, y_prob_clipped))

    # ROC AUC: Base-rate baseline is constant within each date and cannot rank -> "N/A"
    if is_base_rate_baseline:
        auc: float | str = "N/A"
    else:
        auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5
        auc = round(auc, 4)

    # Baseline Brier for BSS
    if baseline_predictions is not None:
        base_resolved = [p for p in baseline_predictions if p.outcome is not None]
        if base_resolved:
            base_true = np.array([p.outcome for p in base_resolved], dtype=np.float64)
            base_prob = np.array([p.probability for p in base_resolved], dtype=np.float64)
            baseline_brier = float(brier_score_loss(base_true, base_prob))
        else:
            p_bar = float(np.mean(y_true))
            baseline_brier = p_bar * (1.0 - p_bar)
    else:
        p_bar = float(np.mean(y_true))
        baseline_brier = p_bar * (1.0 - p_bar)

    bss = 1.0 - brier / baseline_brier if baseline_brier > 0.0 else 0.0

    cal_table = compute_calibration_table(y_true, y_prob)
    economic = compute_economic_spread(resolved)

    return {
        "n_samples": len(resolved),
        "brier_score": round(brier, 4),
        "baseline_brier": round(baseline_brier, 4),
        "brier_skill_score": round(bss, 4),
        "log_loss": round(ll, 4),
        "roc_auc": auc,
        "calibration_table": cal_table,
        "economic": economic,
    }
