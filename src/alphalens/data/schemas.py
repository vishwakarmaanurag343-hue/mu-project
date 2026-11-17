"""Validation primitives and domain schemas for NSE data."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Validates NSE ticker symbols (e.g., TCS.NS, RELIANCE.NS, M&M.NS)
Ticker = Annotated[
    str,
    Field(
        pattern=r"^[A-Z0-9_\-&]+\.NS$",
        description="NSE ticker symbol ending with .NS suffix",
        examples=["TCS.NS", "RELIANCE.NS"],
    ),
]


class TickerInfo(BaseModel):
    """Ticker item returned for autocomplete and universe lookups."""

    model_config = ConfigDict(extra="forbid")

    symbol: Ticker
    name: str
    sector: str


class PricePoint(BaseModel):
    """A single date price and corporate action data point."""

    model_config = ConfigDict(extra="forbid")

    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: int | None = None
    dividend: float | None = None
    split_ratio: float | None = None


class DataQualityReport(BaseModel):
    """Data quality diagnostic metrics and anomaly flags."""

    model_config = ConfigDict(extra="forbid")

    extreme_moves: list[date] = Field(
        default_factory=list,
        description="Dates with absolute daily adjusted return > 20%",
    )
    stale_runs: list[tuple[date, date]] = Field(
        default_factory=list,
        description="Date intervals with 5+ consecutive trading days of identical close or zero volume",
    )
    gaps: list[date] = Field(
        default_factory=list,
        description="Trading dates present in benchmark but missing for the stock",
    )
    adj_close_missing_ratio: float = Field(
        default=0.0,
        description="Proportion of rows missing adjusted close",
    )
    dropped_row_count: int = Field(
        default=0,
        description="Count of corrupted/invalid rows dropped during ingestion",
    )


class PriceSeries(BaseModel):
    """Historical timeseries of equity prices and corporate actions."""

    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    start_date: date
    end_date: date
    points: list[PricePoint]
    quality: DataQualityReport | None = None


class BenchmarkPoint(BaseModel):
    """A single date benchmark index valuation."""

    model_config = ConfigDict(extra="forbid")

    date: date
    value: float


class BenchmarkSeries(BaseModel):
    """Historical timeseries for benchmark performance."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["total_return", "price_only"]
    points: list[BenchmarkPoint]
