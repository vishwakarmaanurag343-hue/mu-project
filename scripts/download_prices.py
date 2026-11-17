"""Download historical price panel for Nifty 50 universe and benchmark.

Usage:
    python scripts/download_prices.py
"""

import time
from datetime import date
from pathlib import Path

import pandas as pd

from alphalens.data.benchmark import load_nifty50_tri
from alphalens.data.prices import YFinancePriceSource
from alphalens.data.universe import load_nifty50_universe


def main() -> None:
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    universe = load_nifty50_universe()
    tickers = [item.symbol for item in universe]
    print(f"Loaded {len(tickers)} tickers from Nifty 50 universe.")

    start_date = date(2014, 1, 1)
    end_date = date.today()
    source = YFinancePriceSource()

    prices_dict: dict[str, dict[date, float]] = {}
    ok_count = 0
    failed_count = 0
    failed_tickers: list[str] = []

    # Check for existing prices.csv to resume if partially downloaded
    prices_csv_path = processed_dir / "prices.csv"
    existing_df: pd.DataFrame | None = None
    if prices_csv_path.exists():
        try:
            existing_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
            print(f"Resuming: found existing prices.csv with {len(existing_df.columns)} tickers.")
        except Exception:
            existing_df = None

    for idx, ticker in enumerate(tickers, start=1):
        print(
            f"[{idx}/{len(tickers)}] Fetching {ticker} ({start_date} to {end_date})...",
            end=" ",
            flush=True,
        )

        if (
            existing_df is not None
            and ticker in existing_df.columns
            and existing_df[ticker].notna().sum() > 500
        ):
            print("Already downloaded. Skipping.")
            prices_dict[ticker] = {
                d.date(): float(v) for d, v in existing_df[ticker].dropna().items()
            }  # type: ignore[union-attr]
            ok_count += 1
            continue

        # Sequential with 2 s pause and rate-limit retries
        max_retries = 3
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                series = source.fetch(ticker, start_date, end_date)
                ticker_prices = {
                    pt.date: pt.adj_close for pt in series.points if pt.adj_close is not None
                }
                if ticker_prices:
                    prices_dict[ticker] = ticker_prices
                    ok_count += 1
                    success = True
                    print(f"OK ({len(ticker_prices)} rows)")
                else:
                    print("Empty response.")
                break
            except Exception as exc:
                if attempt < max_retries and (
                    "Rate limited" in str(exc) or "429" in str(exc) or "timeout" in str(exc).lower()
                ):
                    wait_s = 5 * attempt
                    print(
                        f"Rate limited/timeout on attempt {attempt}. Waiting {wait_s}s...",
                        end=" ",
                        flush=True,
                    )
                    time.sleep(wait_s)
                else:
                    print(f"FAILED: {exc}")
                    break

        if not success and ticker not in prices_dict:
            failed_count += 1
            failed_tickers.append(ticker)

        # 2 s pause between requests to respect public API limits
        time.sleep(2.0)

    # 1. Save adj_close panel to data/processed/prices.csv (date x ticker)
    if prices_dict:
        panel_df = pd.DataFrame(prices_dict)
        panel_df.index.name = "date"
        panel_df = panel_df.sort_index()
        panel_df.to_csv(prices_csv_path)
        print(f"Saved adj_close panel to {prices_csv_path} (shape: {panel_df.shape})")
    else:
        print("Warning: No price data collected!")

    # 2. Save benchmark to data/processed/benchmark.csv
    benchmark_csv_path = processed_dir / "benchmark.csv"
    try:
        benchmark_series = load_nifty50_tri()
        bench_df = pd.DataFrame(
            [{"date": pt.date, "benchmark": pt.value} for pt in benchmark_series.points]
        ).set_index("date")
        bench_df = bench_df.sort_index()
        bench_df.to_csv(benchmark_csv_path)
        print(f"Saved benchmark series to {benchmark_csv_path} (shape: {bench_df.shape})")
    except Exception as exc:
        print(f"Failed to save benchmark: {exc}")

    # Summary
    print("\n" + "=" * 50)
    print("DOWNLOAD SUMMARY:")
    print(f"Tickers OK: {ok_count} / {len(tickers)}")
    print(f"Tickers Failed: {failed_count} ({failed_tickers})")
    if prices_dict and panel_df is not None:
        print(f"Date Range: {panel_df.index.min()} to {panel_df.index.max()}")
    print("=" * 50)


if __name__ == "__main__":
    main()
