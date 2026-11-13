# ADR-001: Market, prediction target, and universe

Status: Accepted · Date: 2026-11-13

## Decision
- Market: India (NSE) only. No SEC EDGAR.
- Target: P(stock's 6-month total return > Nifty 50 total return).
- Universe: Nifty 100, using HISTORICAL constituents at each date
  (avoids survivorship bias).
- Rebalance/evaluation frequency: monthly.
- LLM layer is evaluated forward-only (post model-cutoff dates),
  because LLMs have seen historical outcomes (look-ahead bias).

## Consequences
- Backtest covers the quant engine only.
- Thesis includes ablation: naive baseline vs quant vs quant+LLM.
