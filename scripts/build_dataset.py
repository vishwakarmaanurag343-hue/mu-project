"""Script to build the historical point-in-time factor dataset.

Usage:
    python scripts/build_dataset.py
"""

from pathlib import Path

import pandas as pd

from alphalens.factors.dataset import build_factor_dataset


def main() -> None:
    processed_dir = Path("data/processed")
    prices_path = processed_dir / "prices.csv"
    benchmark_path = processed_dir / "benchmark.csv"

    if not prices_path.exists():
        print(f"Error: {prices_path} not found. Please run scripts/download_prices.py first.")
        return

    if not benchmark_path.exists():
        print(f"Error: {benchmark_path} not found. Please run scripts/download_prices.py first.")
        return

    print("Loading prices and benchmark panels...")
    prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
    bench_df = pd.read_csv(benchmark_path, index_col=0, parse_dates=True)
    bench_series = bench_df.iloc[:, 0]

    print(f"Prices panel shape: {prices_df.shape}, Benchmark observations: {len(bench_series)}")
    print("Building cross-sectional factor dataset...")

    dataset_df = build_factor_dataset(prices_df, bench_series)

    out_path = processed_dir / "dataset.csv"
    dataset_df.to_csv(out_path, index=False)
    print(f"Successfully saved factor dataset to {out_path} (shape: {dataset_df.shape})")

    # Diagnostic Summary
    print("\n" + "=" * 50)
    print("DATASET SUMMARY:")
    print(f"Total Rows: {len(dataset_df)}")
    print(f"Unique Tickers: {dataset_df['ticker'].nunique()}")
    print(f"Date Range: {dataset_df['date'].min()} to {dataset_df['date'].max()}")

    labeled_rows = dataset_df["label"].dropna()
    if len(labeled_rows) > 0:
        base_rate = (labeled_rows == 1).mean()
        print(
            f"Labeled Rows: {len(labeled_rows)} / {len(dataset_df)} ({len(labeled_rows) / len(dataset_df):.1%})"
        )
        print(f"Label Base Rate (Fraction of 1s): {base_rate:.4f} ({base_rate:.1%})")
    else:
        print("No labeled rows.")

    print("\nMissing Values per Factor (Share of None):")
    factor_cols = [
        c
        for c in dataset_df.columns
        if c not in ["date", "ticker", "label", "label_end_date", "excess_6m"]
    ]
    for col in factor_cols:
        missing_share = dataset_df[col].isna().mean()
        print(f"  - {col}: {missing_share:.2%}")
    print("=" * 50)


if __name__ == "__main__":
    main()
