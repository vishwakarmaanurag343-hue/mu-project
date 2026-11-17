# ADR-003: Price and Benchmark Data Ingestion

Status: Accepted · Date: 2026-11-13

## Context
Per ADR-001, AlphaLens requires historical daily price series for the Nifty 100 universe and benchmark total returns for evaluating $P(\text{stock 6m TR} > \text{Nifty 50 TR})$.

Obtaining historical Indian market data involves balancing institutional-grade data accuracy with cost and accessibility:
1. **Stock Prices**: Commercial NSE feeds require substantial subscriptions. Free public alternatives (like Yahoo Finance via `yfinance`) are unofficial and lack SLA guarantees.
2. **Benchmark Returns**: NIFTY 50 price-only returns omit cash dividends (historically $\sim 1.2\text{--}1.6\%$ annual dividend yield), biasing stock excess return calculations upward unless benchmark Total Return Index (TRI) is used.
3. **Network Architecture**: `yfinance` uses its own internal HTTP transport (`requests`/`curl_cffi`) rather than AlphaLens's hardened `SafeHttpClient`.

## Decisions

1. **Price Source Abstraction (`PriceSource` Protocol)**:
   - All analytical factor computation and backtesting engine modules must depend on the `PriceSource` Protocol (`fetch(ticker, start, end) -> PriceSeries`), never directly on `yfinance`.
   - The primary implementation is `YFinancePriceSource`, wrapped with `@cached(namespace="prices")`.
   - Any future migration to an official vendor API (e.g., TrueData, Zerodha Kite, or NSE direct) will require only implementing a new `PriceSource` without changing consumer code.

2. **Adjusted Close for Total Return**:
   - Stock prices are fetched with `auto_adjust=False` and `actions=True` so both nominal `close` and dividend/split-adjusted `adj_close` are preserved alongside corporate action records.
   - Total return timeseries computations exclusively utilize `adj_close`.

3. **Benchmark Selection & Ingestion**:
   - The canonical benchmark is **NIFTY 50 Total Return Index (TRI)**.
   - Ingestion is performed via a verified reference CSV placed at `Settings.reference_dir / "nifty50_tri.csv"`.
   - If the TRI reference CSV is missing, `BenchmarkUnavailable` is raised with explicit guidance on acquiring the file from NSE India.
   - Price-only benchmark fallback (`^NSEI`) is permitted **only** during development when `Settings.allow_price_only_benchmark=True`. A `WARNING` is logged every time this fallback activates. Price-only benchmark data must **never** be used for reported backtests or model calibration.

4. **Accepted Security Risks**:
   - `yfinance` internal networking: Because `yfinance` does not route through `SafeHttpClient`, it bypasses custom pre-flight DNS SSRF checks and domain allowlists. This is accepted as a low-risk trade-off because:
     - Target hostnames are fixed public Yahoo endpoints.
     - Tickers are strictly validated against `Ticker` regex prior to instantiation.
     - All parsed rows pass through schema validation and data quality checks (`DataQualityReport`).

## Consequences

- Clean separation between price ingestion and quant evaluation.
- Protection against dividend yield bias by mandating NIFTY 50 TRI.
- Resilience to corrupt rows via quality flag tracking (`extreme_moves`, `stale_runs`, `gaps`, `adj_close_missing_ratio`).

