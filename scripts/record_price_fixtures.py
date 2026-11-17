"""Utility script to record offline test fixtures for price data and corporate actions.

Run manually with network access enabled:
    python scripts/record_price_fixtures.py

Do NOT run in CI or automated pipelines.
"""

import json
from pathlib import Path

import yfinance as yf


def record_fixtures() -> None:
    target_dir = Path("tests/fixtures/prices")
    target_dir.mkdir(parents=True, exist_ok=True)

    tickers = ["TCS.NS", "INFY.NS", "RELIANCE.NS"]
    start = "2023-01-01"
    end = "2023-06-30"

    for ticker in tickers:
        print(f"Fetching {ticker} from Yahoo Finance...")
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(start=start, end=end, auto_adjust=False, actions=True)
        # Convert to serialized records
        df_reset = df.reset_index()
        # Convert Timestamp to string
        records = []
        for _, row in df_reset.iterrows():
            rec = row.to_dict()
            rec["Date"] = str(rec["Date"])
            records.append(rec)

        out_path = target_dir / f"{ticker.replace('.', '_')}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        print(f"Wrote {len(records)} rows to {out_path}")


if __name__ == "__main__":
    record_fixtures()
