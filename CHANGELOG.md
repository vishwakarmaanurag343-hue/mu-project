# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-13

### Added
- **Point-in-Time Factor Pipeline**:
  - Implemented 6 pure price and risk factors (`mom_12_1`, `mom_6`, `rev_1m`, `vol_6m`, `mdd_12m`, `rel_strength_6m`) in `src/alphalens/factors/price_factors.py`.
  - Date-by-date cross-sectional z-score standardization with $\pm 3\text{ sd}$ winsorization in `src/alphalens/factors/dataset.py`.
  - 126-trading-day forward total return labels vs Nifty 50 TRI benchmark in `src/alphalens/factors/labels.py`.
  - Audited historical price and constituent ingestion scripts (`scripts/download_prices.py`, `scripts/build_dataset.py`).
- **Embargoed Walk-Forward Backtesting & Statistical Corrections**:
  - Walk-forward engine with strict embargo protocol (`label_end_date <= t`) preventing forward window leakage across 119 monthly folds (`2017-01-31` to `2026-11-12`).
  - Implemented Newey-West HAC standard error correction (lag 5) with pure NumPy to account for serial autocorrelation from 6-month overlapping return windows sampled monthly.
  - Common-sample evaluation ($N = 5,332$) across model, momentum baseline, and base-rate baseline; base-rate ROC AUC set to `"N/A"` due to cross-sectional rank invariance.
  - Production model export to `models/model-1.0.json` (JSON only, no pickle) and visual diagnostic report generation (`reports/backtest/`).
- **Quant Prediction Engine & Decision Labels**:
  - Categorical rank-based decision labels across the cross-sectional universe: `"Top quintile (relative strength)"` (top 20%), `"Bottom quintile"` (bottom 20%), and `"Middle"` (remaining 60%).
  - UI warning badge under outperformance probability: *"Backtest shows ranking signal but no calibration skill beyond the base rate; treat the probability as a relative score."*
  - Vectorized Monte Carlo bootstrapping (10,000 paths, seed 42) over 126 trading days producing bear (10th), base (50th), and bull (90th) return scenarios.
  - End-to-end integration with `/api/reports/{ticker}/quant` reading precomputed `CanonicalPrediction` entries with sub-100ms latency.
  - Universe autocomplete endpoint `/api/tickers` backed by Nifty constituent catalog.
- **Security & Privacy Layer**:
  - Hardened `SafeHttpClient` enforcing domain allowlists, manual redirect validation, DNS pre-resolution blocking private/reserved IPs, and streaming size limits.
  - Process-isolated PDF parsing using `multiprocessing.get_context("spawn")` with execution timeouts and memory bounds.
  - DPDP Act compliant notice, consent tracking in `consent_records`, and atomic account deletion with pseudonymised audit logs.
  - Informational banners in UI for preview status of document analysis and graceful SSE handling when LLM provider is unconfigured.
- **Submission Documentation & Automated Demo**:
  - Added comprehensive `README.md`, `docs/RESULTS.md`, `docs/LIMITATIONS_AND_FUTURE_WORK.md`.
  - Created `make demo` target automating the end-to-end pipeline from price download to live application serving.

## [0.1.0] - 2026-11-13

### Added
- Initial project scaffold adhering to production fintech guidelines (ADR-001, ADR-002).
- Base configuration with pydantic-settings and SecretStr masking.
- Fullstack authentication with Argon2id, rotated refresh tokens, and double-submit CSRF.
- Two-tier report layout with React 18, Vite, Tailwind CSS, TanStack Query, and Recharts.
- CI pipeline including backend quality, secret audit, and frontend validation.
