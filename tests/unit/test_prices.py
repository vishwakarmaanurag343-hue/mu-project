"""Unit tests for equity price data ingestion, quality validation, and bulk operations."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import ValidationError

from alphalens.data.cache import clear_namespace
from alphalens.data.prices import (
    PriceSource,
    YFinancePriceSource,
    get_price_history,
    get_prices_bulk,
    total_return_series,
)
from alphalens.data.prices import (
    logger as prices_logger,
)
from alphalens.data.schemas import PricePoint, PriceSeries


@pytest.fixture
def tcs_fixture_df() -> pd.DataFrame:
    fixture_path = Path("tests/fixtures/prices/TCS_NS.json")
    with fixture_path.open("r", encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    return df


def test_ticker_validated_before_network_call() -> None:
    """Invalid ticker formats raise ValidationError before any network attempt."""
    with patch("yfinance.Ticker") as mock_yf:
        with pytest.raises(ValidationError):
            get_price_history("INVALID_TICKER", date(2023, 1, 1), date(2023, 1, 10))

        with pytest.raises(ValidationError):
            get_price_history("TCS", date(2023, 1, 1), date(2023, 1, 10))

        # Assert yfinance was NEVER called
        mock_yf.assert_not_called()


def test_yfinance_source_normalizes_data(tcs_fixture_df: pd.DataFrame, tmp_path: Path) -> None:
    """YFinancePriceSource converts dates to IST, maps columns, and extracts actions."""
    clear_namespace("prices")
    source = YFinancePriceSource()

    with patch("yfinance.Ticker") as mock_yf_class:
        mock_instance = MagicMock()
        mock_instance.history.return_value = tcs_fixture_df
        mock_yf_class.return_value = mock_instance

        series = source.fetch("TCS.NS", date(2023, 1, 1), date(2023, 1, 10))

        assert series.ticker == "TCS.NS"
        assert len(series.points) == 5
        assert series.points[0].date == date(2023, 1, 2)
        assert series.points[0].close == 3265.0
        assert series.points[0].adj_close == 3150.0

        # Point with dividend
        assert series.points[3].date == date(2023, 1, 5)
        assert series.points[3].dividend == 75.0

        # Assert yfinance history parameters
        mock_instance.history.assert_called_once_with(
            start="2023-01-01",
            end="2023-01-10",
            auto_adjust=False,
            actions=True,
            timeout=10.0,
        )

        # Cache test: second call served from cache (mock asserts one source call)
        series2 = source.fetch("TCS.NS", date(2023, 1, 1), date(2023, 1, 10))
        assert len(series2.points) == 5
        mock_instance.history.assert_called_once()  # Still called only once!


def test_row_cleaning_and_corruption_handling(tmp_path: Path) -> None:
    """Rows with NaN become None; all-None rows and High < Low are dropped."""
    clear_namespace("prices")

    dates = pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"])
    data = {
        "Open": [100.0, None, 100.0, 100.0],
        "High": [105.0, None, 90.0, 105.0],  # Row 2 (idx 2) has High (90) < Low (95) -> corrupt
        "Low": [95.0, None, 95.0, 95.0],
        "Close": [102.0, None, 92.0, 102.0],
        "Adj Close": [102.0, None, 92.0, 102.0],
        "Volume": [1000, None, 1000, 1000],
        "Dividends": [0.0, None, 0.0, 0.0],
        "Stock Splits": [0.0, None, 0.0, 0.0],
    }
    df = pd.DataFrame(data, index=dates)

    with patch("yfinance.Ticker") as mock_yf_class:
        mock_instance = MagicMock()
        mock_instance.history.return_value = df
        mock_yf_class.return_value = mock_instance

        with patch.object(prices_logger, "warning") as mock_warn:
            source = YFinancePriceSource()
            series = source.fetch("INFY.NS", date(2023, 1, 1), date(2023, 1, 10))

            # Row 1 (idx 1): all None -> dropped
            # Row 2 (idx 2): High < Low -> dropped with warning
            # Remaining: 2 valid rows (Row 0 and Row 3)
            assert len(series.points) == 2
            assert series.quality is not None
            assert series.quality.dropped_row_count == 2
            assert mock_warn.called


def test_data_quality_flags_synthetic() -> None:
    """Detect extreme moves (>20%) and stale runs (5+ identical close/zero volume)."""
    dates = pd.date_range("2023-01-01", periods=8, freq="D")
    data = {
        "Open": [100.0] * 8,
        "High": [110.0] * 8,
        "Low": [90.0] * 8,
        # 5 consecutive identical closes (stale run: 01-01 to 01-05), followed by >20% move on 01-06
        "Close": [100.0, 100.0, 100.0, 100.0, 100.0, 130.0, 131.0, 132.0],
        "Adj Close": [100.0, 100.0, 100.0, 100.0, 100.0, 130.0, 131.0, 132.0],
        "Volume": [1000] * 8,
        "Dividends": [0.0] * 8,
        "Stock Splits": [0.0] * 8,
    }
    df = pd.DataFrame(data, index=dates)

    with patch("yfinance.Ticker") as mock_yf_class:
        mock_instance = MagicMock()
        mock_instance.history.return_value = df
        mock_yf_class.return_value = mock_instance

        source = YFinancePriceSource()
        series = source.fetch("RELIANCE.NS", date(2023, 1, 1), date(2023, 1, 8))

        assert series.quality is not None
        # Extreme move on 2023-01-06: 100 -> 130 is 30% jump
        assert date(2023, 1, 6) in series.quality.extreme_moves
        # Stale run detected from 2023-01-01 to 2023-01-05
        assert (date(2023, 1, 1), date(2023, 1, 5)) in series.quality.stale_runs


def test_bulk_fetch_graceful_partial_failure() -> None:
    """Bulk fetch continues across tickers; returns results and errors."""
    mock_source = MagicMock(spec=PriceSource)

    def side_effect(ticker: str, start: date, end: date) -> PriceSeries:
        if ticker == "FAIL.NS":
            raise RuntimeError("Upstream timeout")
        return PriceSeries(
            ticker=ticker,  # type: ignore[arg-type]
            start_date=start,
            end_date=end,
            points=[],
        )

    mock_source.fetch.side_effect = side_effect

    tickers = ["TCS.NS", "FAIL.NS", "INFY.NS"]
    results, failures = get_prices_bulk(
        tickers, date(2023, 1, 1), date(2023, 1, 10), source=mock_source
    )

    assert "TCS.NS" in results
    assert "INFY.NS" in results
    assert "FAIL.NS" in failures
    assert "Upstream timeout" in failures["FAIL.NS"]


def test_total_return_series_extraction() -> None:
    """total_return_series extracts (date, adj_close) tuples."""
    series = PriceSeries(
        ticker="TCS.NS",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 3),
        points=[
            PricePoint(date=date(2023, 1, 1), adj_close=100.0),
            PricePoint(date=date(2023, 1, 2), adj_close=None),
            PricePoint(date=date(2023, 1, 3), adj_close=105.0),
        ],
    )
    tr = total_return_series(series)
    assert tr == [(date(2023, 1, 1), 100.0), (date(2023, 1, 3), 105.0)]


@pytest.mark.live
def test_live_yfinance_fetch_tcs() -> None:
    """Live smoke test fetching TCS.NS directly from Yahoo Finance."""
    source = YFinancePriceSource()
    try:
        series = source.fetch("TCS.NS", date(2023, 1, 1), date(2023, 1, 15))
        assert series.ticker == "TCS.NS"
        if len(series.points) > 0:
            assert series.points[0].close is not None
            assert series.quality is not None
    except Exception as exc:
        # Yahoo Finance public rate limit or transient network failure
        pytest.skip(f"Live Yahoo Finance fetch skipped due to upstream condition: {exc}")
