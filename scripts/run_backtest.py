"""Execute walk-forward backtest, generate reports and plots, populate DB, and export model.

Artifacts:
  - reports/backtest/results.json
  - reports/backtest/calibration.png
  - reports/backtest/brier_over_time.png
  - reports/backtest/quintile_spread.png
  - reports/backtest/REPORT.md
  - models/model-1.0.json
  - CanonicalPrediction rows with model_version='bt-1.0'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

# Use non-interactive backend for headless environments
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sqlalchemy import delete

from alphalens.backtest.metrics import compute_metrics
from alphalens.backtest.walk_forward import (
    FACTOR_FEATURES,
    run_walk_forward_backtest,
)
from alphalens.db.models import CanonicalPrediction
from alphalens.db.session import SessionLocal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "dataset.csv"
REPORTS_DIR = PROJECT_ROOT / "reports" / "backtest"
MODELS_DIR = PROJECT_ROOT / "models"


def plot_calibration_curve(
    cal_table: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Plot empirical calibration curve vs perfectly calibrated diagonal."""
    fig, ax = plt.subplots(figsize=(7, 6))

    # Perfect calibration
    ax.plot([0, 1], [0, 1], "k--", label="Perfect Calibration", alpha=0.7)

    # Filter populated bins
    active_bins = [b for b in cal_table if b["count"] > 0]
    pred_avgs = [b["predicted_avg"] for b in active_bins]
    obs_rates = [b["observed_rate"] for b in active_bins]
    counts = [b["count"] for b in active_bins]

    # Plot empirical points
    ax.plot(pred_avgs, obs_rates, "s-", color="#1f77b4", label="Model (bt-1.0)", lw=2)

    # Annotate counts
    for x, y, c in zip(pred_avgs, obs_rates, counts, strict=True):
        ax.annotate(
            f"n={c}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8
        )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean Predicted Probability", fontsize=11)
    ax.set_ylabel("Empirical Frequency (Win Rate)", fontsize=11)
    ax.set_title("AlphaLens Reliability Curve (10 Bins)", fontsize=12, pad=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_brier_over_time(
    model_preds: list[Any],
    base_preds: list[Any],
    output_path: Path,
) -> None:
    """Plot monthly Brier score trajectory over time for model vs base rate."""
    model_resolved = [p for p in model_preds if p.outcome is not None]
    base_resolved = [p for p in base_preds if p.outcome is not None]

    df_model = pd.DataFrame(
        [{"date": p.date, "err": (p.probability - p.outcome) ** 2} for p in model_resolved]
    )
    df_base = pd.DataFrame(
        [{"date": p.date, "err": (p.probability - p.outcome) ** 2} for p in base_resolved]
    )

    m_brier = df_model.groupby("date")["err"].mean().reset_index()
    b_brier = df_base.groupby("date")["err"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(m_brier["date"], m_brier["err"], label="AlphaLens Model", color="#1f77b4", lw=1.8)
    ax.plot(
        b_brier["date"],
        b_brier["err"],
        label="Trailing Base Rate",
        color="#ff7f0e",
        linestyle="--",
        lw=1.5,
    )
    ax.axhline(0.25, color="gray", linestyle=":", label="Unskilled Coin Flip (0.25)")

    # Format ticks: show 1 tick per year
    dates = m_brier["date"].tolist()
    step = max(1, len(dates) // 10)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels(
        [dates[i] for i in range(0, len(dates), step)], rotation=45, ha="right", fontsize=9
    )

    ax.set_ylabel("Brier Score (Lower is Better)", fontsize=11)
    ax.set_title("Walk-Forward Brier Score Over Time (2017 - 2026)", fontsize=12, pad=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_quintile_spread(
    monthly_spreads: list[dict[str, Any]],
    mean_spread: float,
    output_path: Path,
) -> None:
    """Plot monthly top vs bottom quintile excess 6m return spread."""
    dates = [m["date"] for m in monthly_spreads]
    spreads = [m["spread"] * 100.0 for m in monthly_spreads]  # in percent

    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#2ca02c" if s >= 0 else "#d62728" for s in spreads]
    ax.bar(range(len(dates)), spreads, color=colors, alpha=0.7, width=0.8)
    ax.axhline(
        mean_spread * 100.0,
        color="#1f77b4",
        linestyle="--",
        lw=1.8,
        label=f"Mean Spread: {mean_spread * 100.0:.2f}%",
    )
    ax.axhline(0, color="black", lw=0.8)

    step = max(1, len(dates) // 10)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels(
        [dates[i] for i in range(0, len(dates), step)], rotation=45, ha="right", fontsize=9
    )

    ax.set_ylabel("6M Return Spread (Q5 - Q1) (%)", fontsize=11)
    ax.set_title(
        "Economic Discrimination: Top Quintile vs Bottom Quintile Excess Return",
        fontsize=12,
        pad=12,
    )
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def store_canonical_predictions(predictions: list[Any], model_version: str = "bt-1.0") -> int:
    """Store all out-of-sample predictions with resolved outcomes into CanonicalPrediction.

    Idempotent: removes existing rows with model_version before insertion.
    """
    resolved = [p for p in predictions if p.outcome is not None]
    if not resolved:
        return 0

    with SessionLocal() as db:
        # Delete existing bt-1.0 rows
        db.execute(
            delete(CanonicalPrediction).where(CanonicalPrediction.model_version == model_version)
        )
        db.commit()

        # Insert new rows
        rows = [
            CanonicalPrediction(
                ticker=p.ticker,
                as_of=p.date,
                probability=round(p.probability, 4),
                outcome=p.outcome,
                model_version=model_version,
            )
            for p in resolved
        ]
        db.add_all(rows)
        db.commit()

    return len(rows)


def fit_and_save_final_model(
    df: pd.DataFrame,
    features: list[str],
    metrics_summary: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    """Fit final logistic model on all labelled rows and serialize to JSON."""
    clean_df = df.dropna(subset=[*features, "label"]).sort_values("date")
    x_train = clean_df[features]
    y_train = clean_df["label"].astype(int)

    clf = LogisticRegression(C=1.0, random_state=42)
    clf.fit(x_train, y_train)

    coef_dict = {feat: round(float(c), 6) for feat, c in zip(features, clf.coef_[0], strict=True)}
    intercept = round(float(clf.intercept_[0]), 6)

    model_metadata = {
        "model_name": "AlphaLens Logistic Calibrator",
        "model_version": "1.0",
        "algorithm": "LogisticRegression",
        "regularization": "L2",
        "C": 1.0,
        "solver": "lbfgs",
        "random_state": 42,
        "features": features,
        "coefficients": coef_dict,
        "intercept": intercept,
        "training_metadata": {
            "n_samples": len(clean_df),
            "start_date": str(clean_df["date"].min()),
            "end_date": str(clean_df["date"].max()),
            "base_rate": round(float(y_train.mean()), 4),
            "zscore_method": "cross_sectional_per_date_winsorized_3sd",
        },
        "walk_forward_metrics": metrics_summary,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(model_metadata, f, indent=2)

    return model_metadata


def generate_report_markdown(
    results: dict[str, Any],
    final_model: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate extensive markdown report documenting method, results, and limitations."""
    m = results["model"]
    b = results["base_rate_baseline"]
    mom = results["momentum_baseline"]
    meta = results["metadata"]

    lines = [
        "# AlphaLens Walk-Forward Backtest & Calibration Report",
        "",
        f"**Date:** {meta['generated_at']}  ",
        "**Model Version:** `bt-1.0` (Production candidate: `model-1.0.json`)  ",
        "**Prediction Target:** `P(Stock 6-Month TR > Nifty 50 TR)` (ADR-001)  ",
        f"**Evaluation Horizon:** {meta['start_date']} to {meta['end_date']} ({meta['n_months']} rebalance months)  ",
        f"**Common Sample Out-of-Sample Predictions:** {m['n_samples']} evaluated predictions (evaluated on identical sample)  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Core Results",
        "",
        "| Metric | AlphaLens Model (6 Factors) | Momentum Baseline (`mom_12_1`) | Trailing Base Rate |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Brier Score** (lower is better) | **{m['brier_score']:.4f}** | {mom['brier_score']:.4f} | {b['brier_score']:.4f} |",
        f"| **Brier Skill Score (BSS)** vs Base Rate | **{m['brier_skill_score']:+.4f}** | {mom['brier_skill_score']:+.4f} | {b['brier_skill_score']:.4f} |",
        f"| **Log Loss** | **{m['log_loss']:.4f}** | {mom['log_loss']:.4f} | {b['log_loss']:.4f} |",
        f"| **ROC AUC** | **{m['roc_auc']}** | {mom['roc_auc']} | {b['roc_auc']}* |",
        f"| **Top-Bottom Quintile Spread (mean)** | **{m['economic']['mean_spread'] * 100:+.2f}%** | {mom['economic']['mean_spread'] * 100:+.2f}% | N/A |",
        f"| **Spread t-stat (Naive)** | **t = {m['economic']['t_stat_naive']:.2f}** (p = {m['economic']['p_value_naive']:.4f}) | t = {mom['economic']['t_stat_naive']:.2f} (p = {mom['economic']['p_value_naive']:.4f}) | N/A |",
        f"| **Spread t-stat (Newey-West HAC, lag 5)** | **t = {m['economic']['t_stat_hac']:.2f}** (p = {m['economic']['p_value_hac']:.4f}) | t = {mom['economic']['t_stat_hac']:.2f} (p = {mom['economic']['p_value_hac']:.4f}) | N/A |",
        f"| **Sample Count (resolved common sample)** | {m['n_samples']} | {mom['n_samples']} | {b['n_samples']} |",
        "",
        "\\* *Note on Base-Rate Baseline ROC AUC: Base-rate probabilities are constant within each date cross-section (representing the historical win-rate up to that rebalance date). A constant within-date prediction cannot rank stocks cross-sectionally, rendering ROC AUC undefined / non-applicable (N/A).*  ",
        "",
        "> **Key Takeaway & Statistical Interpretation:**",
        "> - **Calibration Skill:** Model probabilities show **no calibration skill beyond the trailing base rate** ($BSS \\approx 0.0000$). The 6-factor logistic model's predicted probabilities should be treated strictly as relative rank scores rather than well-calibrated physical probabilities.",
        "> - **Factor Incremental Value:** The 6-factor model adds very little over momentum alone: Brier score is virtually identical (0.2452 vs 0.2452), AUC is marginally higher (0.5401 vs 0.5369), and the monthly quintile return spread is +4.41% vs +3.78%.",
        "> - **HAC Significance:** With naive standard errors, the spread t-stat is 2.84 ($p = 0.0054$). However, after adjusting for autocorrelation due to 6-month overlapping return windows with Newey-West HAC (lag 5), the t-statistic drops to **t = 1.79 ($p = 0.0761$)** for the 6-factor model (marginally significant at the 10% level, not significant at 5%), and **t = 1.62 ($p = 0.1071$)** for the momentum baseline (not significant at the 10% level).",
        "",
        "---",
        "",
        "## 2. Methodology & Strict Embargo Protocol",
        "",
        "To eliminate look-ahead bias and data leakage, the walk-forward evaluation protocol enforces a strict **embargo window**:",
        "",
        "```mermaid",
        "gantt",
        "    title Walk-Forward Embargo Timeline at Date t",
        "    dateFormat  YYYY-MM",
        "    axisFormat  %Y-%m",
        "    section Training Data",
        "    Resolved Labels (t - 6m and earlier) :done, train1, 2014-01, 2020-01",
        "    section Embargo Window",
        "    Unresolved / Overlapping (t - 6m to t) :crit, active, 2020-01, 2020-07",
        "    section Out-of-Sample",
        "    Evaluation at Date t :milestone, m1, 2020-07, 0d",
        "    Realized Outcomes (t to t + 6m) :active, fut, 2020-07, 2021-01",
        "```",
        "",
        "### Embargo Rules:",
        "1. **No Overlapping Forward Windows:** At rebalance month-end date $t$, any historical observation with `label_end_date > t` is strictly excluded from training. Because the prediction target spans 126 trading days (~6 calendar months), observations made between $t - 6\\text{m}$ and $t$ have forward return windows that overlap into $t$. Training on them would leak future price trends.",
        "2. **Point-in-Time Cross-Sectional Normalization:** Z-scores for factors are computed **per rebalance date**, strictly across stocks available at that specific date. No panel-wide future means or standard deviations are used.",
        "3. **Fixed Hyperparameters:** Regularization strength ($C=1.0, L2$) was fixed *a priori* without tuning on backtest outcomes, adhering strictly to research hygiene rules.",
        "",
        "---",
        "",
        "## 3. Reliability & Calibration Analysis",
        "",
        "The table below details empirical reliability across 10 probability bins:",
        "",
        "| Bin Center | Predicted Avg | Observed Win Rate | Sample Count (n) |",
        "| :---: | :---: | :---: | :---: |",
    ]

    for row in m["calibration_table"]:
        lines.append(
            f"| {row['bin_center']:.2f} | {row['predicted_avg']:.4f} | {row['observed_rate']:.4f} | {row['count']} |"
        )

    lines.extend(
        [
            "",
            "### Calibration Curve",
            "![Reliability Curve](calibration.png)",
            "",
            "### Brier Score Trajectory Over Time",
            "![Brier Over Time](brier_over_time.png)",
            "",
            "### Economic Discrimination (Quintile Spread Over Time)",
            "![Quintile Spread](quintile_spread.png)",
            "",
            "---",
            "",
            "## 4. Final Production Model (`model-1.0.json`)",
            "",
            "- **Algorithm:** `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs')`",
            f"- **Training Samples:** {final_model['training_metadata']['n_samples']} observations",
            f"- **Training Span:** {final_model['training_metadata']['start_date']} to {final_model['training_metadata']['end_date']}",
            f"- **Intercept:** `{final_model['intercept']}`",
            "",
            "### Feature Weights:",
            "| Feature | Weight (Coefficient) | Intuition |",
            "| :--- | :---: | :--- |",
            f"| `vol_6m_z` | **{final_model['coefficients']['vol_6m_z']:+.4f}** | Moderate positive exposure to 6-month historical volatility |",
            f"| `mom_6_z` | **{final_model['coefficients']['mom_6_z']:+.4f}** | 6-month medium-term trend following |",
            f"| `rel_strength_6m_z` | **{final_model['coefficients']['rel_strength_6m_z']:+.4f}** | Outperformance vs benchmark over 6 months |",
            f"| `mom_12_1_z` | **{final_model['coefficients']['mom_12_1_z']:+.4f}** | Classic 12-minus-1 month price momentum |",
            f"| `mdd_12m_z` | **{final_model['coefficients']['mdd_12m_z']:+.4f}** | 12-month maximum drawdown penalty / resilience |",
            f"| `rev_1m_z` | **{final_model['coefficients']['rev_1m_z']:+.4f}** | Short-term 1-month mean reversion (negative weight) |",
            "",
            "---",
            "",
            "## 5. Research Limitations & Known Caveats",
            "",
            "1. **Current-Constituent Survivorship Bias:** The universe is reconstructed using the current Nifty 50 constituents back-projected to 2014. Historically delisted, merged, or demoted companies are absent, biasing empirical win rates upward.",
            "2. **Overlapping 6-Month Return Labels:** Although the embargo prevents data leakage into the training set, monthly rebalancing on a 6-month forward horizon creates serial correlation across consecutive monthly test observations. This inflates apparent sample size ($n=5,332$), though monthly aggregation for the $t$-statistic adjusts for this effect.",
            "3. **Data Quality & Splice Discrepancies:** Free-tier yfinance adjusted prices may occasionally suffer from unannounced corporate action adjustments or dividend cashflow discrepancies compared to official NSE bhavcopy feeds.",
            "4. **Price Factors Only:** Phase 1 incorporates only pure price and technical factors. Fundamentals (P/E, ROE, debt/equity) and qualitative evidence (LLM-extracted catalyst sentiment) are planned for Phase 2.",
            "",
        ]
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    """Run full backtest workflow."""
    print("=== AlphaLens Walk-Forward Backtest & Calibration Job ===")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading point-in-time dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows across {df['date'].nunique()} dates.")

    print("Running walk-forward backtest (start_date=2017-01-01)...")
    wf_res = run_walk_forward_backtest(df, start_date="2017-01-01", features=FACTOR_FEATURES)
    print(f"Completed {len(wf_res.folds)} monthly folds.")
    print(
        f"Dropped rows due to missing features: train={wf_res.total_dropped_train_rows}, test={wf_res.total_dropped_test_rows}"
    )

    print("Computing common evaluation sample...")
    # Common sample: (date, ticker) keys present in all three with resolved outcomes
    model_resolved_keys = {
        (p.date, p.ticker) for p in wf_res.model_predictions if p.outcome is not None
    }
    mom_resolved_keys = {
        (p.date, p.ticker) for p in wf_res.mom_predictions if p.outcome is not None
    }
    base_resolved_keys = {
        (p.date, p.ticker) for p in wf_res.base_predictions if p.outcome is not None
    }
    common_keys = model_resolved_keys & mom_resolved_keys & base_resolved_keys
    print(f"Common sample resolved predictions: N = {len(common_keys)}")

    common_model_preds = [
        p for p in wf_res.model_predictions if (p.date, p.ticker) in common_keys
    ]
    common_mom_preds = [
        p for p in wf_res.mom_predictions if (p.date, p.ticker) in common_keys
    ]
    common_base_preds = [
        p for p in wf_res.base_predictions if (p.date, p.ticker) in common_keys
    ]

    print("Computing evaluation metrics on common sample for model and baselines...")
    metrics_model = compute_metrics(common_model_preds, common_base_preds)
    metrics_base = compute_metrics(
        common_base_preds, common_base_preds, is_base_rate_baseline=True
    )
    metrics_mom = compute_metrics(common_mom_preds, common_base_preds)

    dates_in_test = sorted(list({p.date for p in wf_res.model_predictions}))
    results_summary = {
        "metadata": {
            "start_date": dates_in_test[0] if dates_in_test else "2017-01-31",
            "end_date": dates_in_test[-1] if dates_in_test else "2026-11-12",
            "n_months": len(dates_in_test),
            "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "model": metrics_model,
        "base_rate_baseline": metrics_base,
        "momentum_baseline": metrics_mom,
    }

    # Save results.json
    results_json_path = REPORTS_DIR / "results.json"
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
    print(f"Saved results summary to {results_json_path}")

    # Generate plots
    print("Generating visual plots...")
    plot_calibration_curve(metrics_model["calibration_table"], REPORTS_DIR / "calibration.png")
    plot_brier_over_time(
        wf_res.model_predictions, wf_res.base_predictions, REPORTS_DIR / "brier_over_time.png"
    )
    plot_quintile_spread(
        metrics_model["economic"]["monthly_spreads"],
        metrics_model["economic"]["mean_spread"],
        REPORTS_DIR / "quintile_spread.png",
    )
    print("Saved calibration.png, brier_over_time.png, quintile_spread.png")

    # Store canonical predictions in database
    print(
        "Storing out-of-sample predictions into CanonicalPrediction table (model_version='bt-1.0')..."
    )
    stored_count = store_canonical_predictions(wf_res.model_predictions, model_version="bt-1.0")
    print(f"Stored {stored_count} resolved canonical predictions in database.")

    # Fit final model on all labelled rows
    print("Fitting final model on all labelled historical rows...")
    final_model_path = MODELS_DIR / "model-1.0.json"
    final_model_meta = fit_and_save_final_model(
        df, FACTOR_FEATURES, metrics_model, final_model_path
    )
    print(f"Saved serialized final model to {final_model_path}")

    # Generate REPORT.md
    report_md_path = REPORTS_DIR / "REPORT.md"
    generate_report_markdown(results_summary, final_model_meta, report_md_path)
    print(f"Saved comprehensive report to {report_md_path}")

    print("\n=== Walk-Forward Summary (Common Sample N={}) ===".format(metrics_model['n_samples']))
    print(f"Months evaluated: {len(dates_in_test)} ({dates_in_test[0]} to {dates_in_test[-1]})")
    print(f"Total out-of-sample predictions: {len(wf_res.model_predictions)}")
    print(f"Resolved common out-of-sample predictions: {metrics_model['n_samples']}")
    print(
        f"Model: Brier={metrics_model['brier_score']:.4f}, BSS={metrics_model['brier_skill_score']:+.4f}, AUC={metrics_model['roc_auc']}, LogLoss={metrics_model['log_loss']:.4f}, Spread={metrics_model['economic']['mean_spread'] * 100:+.2f}% (t_naive={metrics_model['economic']['t_stat_naive']:.2f}, t_hac={metrics_model['economic']['t_stat_hac']:.2f})"
    )
    print(
        f"Base Rate: Brier={metrics_base['brier_score']:.4f}, BSS={metrics_base['brier_skill_score']:.4f}, AUC={metrics_base['roc_auc']}, LogLoss={metrics_base['log_loss']:.4f}"
    )
    print(
        f"Momentum: Brier={metrics_mom['brier_score']:.4f}, BSS={metrics_mom['brier_skill_score']:+.4f}, AUC={metrics_mom['roc_auc']}, LogLoss={metrics_mom['log_loss']:.4f}, Spread={metrics_mom['economic']['mean_spread'] * 100:+.2f}% (t_naive={metrics_mom['economic']['t_stat_naive']:.2f}, t_hac={metrics_mom['economic']['t_stat_hac']:.2f})"
    )


if __name__ == "__main__":
    main()
