"""Dataset builder combining cross-sectional price factors and forward labels.

Produces rows of:
(date, ticker, raw factors, z-scored factors, excess_6m, label, label_end_date)
Z-scores computed cross-sectionally PER DATE only (winsorised at +/- 3 sd).
"""

import numpy as np
import pandas as pd

from alphalens.factors.labels import compute_label
from alphalens.factors.price_factors import compute_all_factors, compute_month_ends

FACTOR_NAMES = [
    "mom_12_1",
    "mom_6",
    "rev_1m",
    "vol_6m",
    "mdd_12m",
    "rel_strength_6m",
]


def cross_sectional_zscore(df_slice: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    """Compute cross-sectional z-scores per date slice, winsorised at +/- 3 standard deviations.

    z = (x - mean) / std.
    Winsorize to [-3.0, 3.0].
    If std == 0 or count < 2 -> z-score is NaN.
    """
    z_df = pd.DataFrame(index=df_slice.index)
    for col in factor_cols:
        series = df_slice[col].dropna()
        if len(series) < 2:
            z_df[f"{col}_z"] = np.nan
            continue

        mean = series.mean()
        std = series.std(ddof=1)
        if std == 0 or np.isnan(std):
            z_df[f"{col}_z"] = np.nan
            continue

        z = (df_slice[col] - mean) / std
        # Winsorise at +/- 3
        z_winsor = z.clip(lower=-3.0, upper=3.0)
        z_df[f"{col}_z"] = z_winsor

    return z_df


def build_factor_dataset(
    prices_df: pd.DataFrame,
    benchmark_series: pd.Series,
) -> pd.DataFrame:
    """Build panel dataset of monthly point-in-time factors, z-scores, and labels.

    prices_df: DataFrame of adjusted close prices indexed by date (rows = dates, columns = tickers).
    benchmark_series: Series of benchmark index values indexed by date.
    """
    # Standardize index to date objects
    if isinstance(prices_df.index, pd.DatetimeIndex):
        trading_dates = [d.date() for d in prices_df.index]
        prices_df.index = pd.Index(trading_dates)

    if isinstance(benchmark_series.index, pd.DatetimeIndex):
        bench_dates = [d.date() for d in benchmark_series.index]
        benchmark_series.index = pd.Index(bench_dates)

    # Calculate month-end evaluation dates
    month_ends = compute_month_ends(list(prices_df.index))
    tickers = list(prices_df.columns)

    records: list[dict[str, object]] = []

    for t in month_ends:
        for ticker in tickers:
            stock_series = prices_df[ticker].dropna()
            if stock_series.empty or stock_series.index.min() > t:
                continue

            factors = compute_all_factors(stock_series, benchmark_series, t)
            excess, label, label_end_date = compute_label(stock_series, benchmark_series, t)

            rec: dict[str, object] = {
                "date": t,
                "ticker": ticker,
                **factors,
                "excess_6m": excess,
                "label": label,
                "label_end_date": label_end_date,
            }
            records.append(rec)

    if not records:
        return pd.DataFrame()

    raw_df = pd.DataFrame(records)

    # Compute cross-sectional z-scores per date
    z_scored_groups: list[pd.DataFrame] = []
    for _d, group in raw_df.groupby("date"):
        z_slice = cross_sectional_zscore(group, FACTOR_NAMES)
        merged_slice = pd.concat([group, z_slice], axis=1)
        z_scored_groups.append(merged_slice)

    final_df = (
        pd.concat(z_scored_groups, axis=0).sort_values(by=["date", "ticker"]).reset_index(drop=True)
    )

    # Reorder columns logically
    z_cols = [f"{col}_z" for col in FACTOR_NAMES]
    ordered_cols = [
        "date",
        "ticker",
        *FACTOR_NAMES,
        *z_cols,
        "excess_6m",
        "label",
        "label_end_date",
    ]
    final_df = final_df[ordered_cols]
    return final_df
