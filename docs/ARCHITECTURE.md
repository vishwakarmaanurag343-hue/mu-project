# AlphaLens Architecture

## Overview
AlphaLens is an industry-grade, evidence-cited, calibrated equity research assistant for the National Stock Exchange of India (NSE).

## System Architecture

```
[ React 18 + TS Client (Vite) ]
               │
      (HTTP / SSE / REST)
               ▼
   [ FastAPI Backend Service ]
       ├── Static Serving (dist/) & Same-Origin Proxy
       ├── Security Middleware (CSP, CSRF, Secure Cookies)
       ├── Routing & Authentication
       ▼
   [ Core Quantitative & LLM Engine ]
       ├── Factors Engine (Value, Quality, Momentum, Volatility)
       ├── Backtest Engine (Walk-forward historical evaluation)
       ├── LLM Evidence Pipeline (SSE streamed, forward-only evaluation)
       ▼
   [ Data Storage & Caching Layer ]
       ├── PostgreSQL / SQLite via SQLAlchemy
       ├── Vector Store (ChromaDB)
       └── Cache Directory (Precomputed factors & LLM summaries)
```

## Key Architectural Decisions
1. **Target**: P(stock's 6-month total return > Nifty 50 total return).
2. **Universe**: Nifty 100 historical constituents per rebalance date (survivorship bias prevention).
3. **Same-Origin Deployment**: FastAPI serves built frontend assets and exposes `/api` endpoints.
4. **Precompute & Streaming**: Daily/nightly precompute of quantitative factors; progressive streaming of LLM synthesis via Server-Sent Events (SSE).
