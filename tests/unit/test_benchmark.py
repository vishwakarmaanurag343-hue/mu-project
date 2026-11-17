"""Unit tests for NIFTY 50 benchmark loader and gap calculation."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alphalens.config import Settings
from alphalens.data.benchmark import compute_stock_gaps, load_nifty50_tri
from alphalens.data.errors import BenchmarkUnavailable
from alphalens.data.schemas import BenchmarkPoint, BenchmarkSeries, PricePoint, PriceSeries


def test_load_nifty50_tri_valid_csv(tmp_path: Path) -> None:
    """Valid NIFTY 50 TRI CSV loads chronologically with positive values."""
    csv_file = tmp_path / "nifty50_tri.csv"
    csv_content = """Date,Total Returns Index
01-Jan-2023,24000.50
02-Jan-2023,24150.20
03-Jan-2023,24100.80
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    series = load_nifty50_tri(reference_path=csv_file)
    assert series.name == "NIFTY 50 Total Returns Index"
    assert series.kind == "total_return"
    assert len(series.points) == 3
    assert series.points[0].date == date(2023, 1, 1)
    assert series.points[0].value == 24000.50
    assert series.points[1].date == date(2023, 1, 2)


def test_load_nifty50_tri_malformed_csv_rejected(tmp_path: Path) -> None:
    """CSV with missing columns or negative values is rejected."""
    # 1. Missing TRI column
    bad_cols_file = tmp_path / "bad_cols.csv"
    bad_cols_file.write_text("Date,Volume\n2023-01-01,1000\n", encoding="utf-8")
    with pytest.raises(BenchmarkUnavailable) as exc:
        load_nifty50_tri(reference_path=bad_cols_file)
    assert "missing required Date or TRI column" in str(exc.value)

    # 2. Negative value
    negative_file = tmp_path / "negative.csv"
    negative_file.write_text("Date,Total Returns Index\n2023-01-01,-10.0\n", encoding="utf-8")
    with pytest.raises(BenchmarkUnavailable) as exc:
        load_nifty50_tri(reference_path=negative_file)
    assert "must be positive" in str(exc.value)

    # 3. Bad date
    bad_date_file = tmp_path / "bad_date.csv"
    bad_date_file.write_text("Date,Total Returns Index\nnot-a-date,100.0\n", encoding="utf-8")
    with pytest.raises(BenchmarkUnavailable) as exc:
        load_nifty50_tri(reference_path=bad_date_file)
    assert "Unable to parse date format" in str(exc.value)


def test_missing_benchmark_file_behavior(tmp_path: Path) -> None:
    """Missing CSV raises BenchmarkUnavailable unless allow_price_only_benchmark is enabled."""
    missing_file = tmp_path / "missing.csv"

    # Default settings: allow_price_only_benchmark is False -> raises BenchmarkUnavailable
    with patch("alphalens.data.benchmark.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            reference_dir=tmp_path,
            allow_price_only_benchmark=False,
        )
        with pytest.raises(BenchmarkUnavailable) as exc:
            load_nifty50_tri(reference_path=missing_file)
        assert "Benchmark reference file not found" in str(exc.value)

    # When allow_price_only_benchmark is True -> falls back to ^NSEI with warning
    with patch("alphalens.data.benchmark.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            reference_dir=tmp_path,
            allow_price_only_benchmark=True,
        )
        import pandas as pd

        fallback_df = pd.DataFrame(
            {"Close": [18000.0, 18100.0]},
            index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
        )
        with patch("yfinance.Ticker") as mock_yf:
            mock_inst = MagicMock()
            mock_inst.history.return_value = fallback_df
            mock_yf.return_value = mock_inst

            with patch("logging.Logger.warning") as mock_warn:
                fallback_series = load_nifty50_tri(reference_path=missing_file)
                assert fallback_series.kind == "price_only"
                assert len(fallback_series.points) == 2
                assert mock_warn.called


def test_compute_stock_gaps() -> None:
    """compute_stock_gaps flags trading calendar days missing in stock series."""
    benchmark = BenchmarkSeries(
        name="NIFTY 50 TRI",
        kind="total_return",
        points=[
            BenchmarkPoint(date=date(2023, 1, 2), value=100.0),
            BenchmarkPoint(date=date(2023, 1, 3), value=101.0),
            BenchmarkPoint(date=date(2023, 1, 4), value=102.0),
            BenchmarkPoint(date=date(2023, 1, 5), value=103.0),
        ],
    )
    # Stock is missing 2023-01-03
    stock = PriceSeries(
        ticker="TCS.NS",
        start_date=date(2023, 1, 2),
        end_date=date(2023, 1, 5),
        points=[
            PricePoint(date=date(2023, 1, 2), close=3200.0),
            PricePoint(date=date(2023, 1, 4), close=3220.0),
            PricePoint(date=date(2023, 1, 5), close=3250.0),
        ],
    )

    gaps = compute_stock_gaps(stock, benchmark)
    assert gaps == [date(2023, 1, 3)]
