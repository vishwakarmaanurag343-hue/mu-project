"""Benchmark timeseries loader and Nifty 50 Total Return Index integration."""

import csv
from datetime import date, datetime
from pathlib import Path

import structlog

from alphalens.config import get_settings
from alphalens.data.errors import BenchmarkUnavailable
from alphalens.data.schemas import (
    BenchmarkPoint,
    BenchmarkSeries,
    PriceSeries,
)

logger = structlog.get_logger("alphalens.data.benchmark")


def load_nifty50_tri(reference_path: Path | None = None) -> BenchmarkSeries:
    """Load canonical NIFTY 50 Total Return Index (TRI) from manual reference CSV.

    Validates schema, sorts dates, prunes duplicates, and verifies positive index values.
    If reference CSV is missing, falls back to ^NSEI only when
    allow_price_only_benchmark is enabled.
    """
    settings = get_settings()
    target_path = reference_path or (settings.reference_dir / "nifty50_tri.csv")

    if not target_path.exists():
        if settings.allow_price_only_benchmark:
            logger.warning(
                "benchmark_fallback_price_only",
                target_path=str(target_path),
                fallback_symbol="^NSEI",
            )
            # Fetch ^NSEI directly via yfinance
            import yfinance as yf

            yf_ticker = yf.Ticker("^NSEI")
            df = yf_ticker.history(start="2010-01-01", auto_adjust=False, timeout=10.0)
            fallback_points: list[BenchmarkPoint] = []
            if not df.empty:
                for idx, row in df.iterrows():
                    c_val = row.get("Close")
                    if (
                        c_val is not None
                        and not (isinstance(c_val, float) and c_val != c_val)
                        and c_val > 0
                    ):
                        fallback_points.append(
                            BenchmarkPoint(
                                date=idx.date() if hasattr(idx, "date") else idx,
                                value=float(c_val),
                            )
                        )

            return BenchmarkSeries(
                name="NIFTY 50 (Price Only Fallback)",
                kind="price_only",
                points=fallback_points,
            )

        raise BenchmarkUnavailable(
            f"Benchmark reference file not found at '{target_path}'. "
            "Please download historical NIFTY 50 TRI data from NSE India "
            "(https://www.nseiindia.com/reports-indices-historical-data) and place it as a CSV at "
            f"'{target_path}'. Refer to docs/data/benchmark.md for instructions."
        )

    # Parse and validate the reference CSV
    points: list[BenchmarkPoint] = []
    seen_dates: set[date] = set()

    with target_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise BenchmarkUnavailable(f"Malformed or empty CSV at '{target_path}'")

        # Normalize column lookup
        field_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}
        date_col = field_map.get("date")
        val_col = (
            field_map.get("total_returns_index")
            or field_map.get("tri")
            or field_map.get("close")
            or field_map.get("index_value")
        )

        if not date_col or not val_col:
            msg = f"CSV at '{target_path}' missing required Date or TRI column (found {reader.fieldnames})"
            raise BenchmarkUnavailable(msg)

        for row_idx, row in enumerate(reader, start=2):
            raw_date = row.get(date_col)
            raw_val = row.get(val_col)

            if not raw_date or not raw_val:
                continue

            # Parse date (supports ISO YYYY-MM-DD or DD-MMM-YYYY commonly exported by NSE)
            parsed_date: date | None = None
            date_clean = raw_date.strip()
            for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    parsed_date = datetime.strptime(date_clean, fmt).date()
                    break
                except ValueError:
                    pass

            if parsed_date is None:
                raise BenchmarkUnavailable(
                    f"Row {row_idx}: Unable to parse date format from '{raw_date}'"
                )

            try:
                clean_val_str = raw_val.strip().replace(",", "")
                float_val = float(clean_val_str)
            except ValueError as e:
                raise BenchmarkUnavailable(
                    f"Row {row_idx}: Invalid numeric value '{raw_val}' in {val_col}"
                ) from e

            if float_val <= 0:
                raise BenchmarkUnavailable(
                    f"Row {row_idx}: Benchmark value must be positive (got {float_val})"
                )

            if parsed_date in seen_dates:
                # Deduplicate: skip already encountered date
                continue

            seen_dates.add(parsed_date)
            points.append(BenchmarkPoint(date=parsed_date, value=float_val))

    # Sort points chronologically
    points.sort(key=lambda p: p.date)

    return BenchmarkSeries(
        name="NIFTY 50 Total Returns Index",
        kind="total_return",
        points=points,
    )


def compute_stock_gaps(stock_series: PriceSeries, benchmark_series: BenchmarkSeries) -> list[date]:
    """Identify trading calendar dates present in benchmark but missing in stock series."""
    stock_dates = {p.date for p in stock_series.points}
    start = stock_series.start_date
    end = stock_series.end_date

    gaps = [
        bp.date
        for bp in benchmark_series.points
        if start <= bp.date <= end and bp.date not in stock_dates
    ]
    return sorted(gaps)
