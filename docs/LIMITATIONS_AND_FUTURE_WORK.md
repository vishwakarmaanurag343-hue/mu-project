# Research Limitations & Future Work

---

## 1. Documented Research Limitations

### 1. Survivorship Bias (Constituent Selection)
- **Current Limitation**: The dataset is formed using current constituents of the Nifty 50 index back-projected to 2014. Equities that underperformed, underwent insolvency, merged, or were demoted from the benchmark over the 2014–2026 window are omitted.
- **Consequence**: This inflates the empirical baseline win rate (~56.4%) and introduces survivorship bias into historical factor z-scores.

### 2. Free-Tier Market Data Fidelity (`yfinance`)
- **Current Limitation**: Price data is collected via Yahoo Finance.
- **Consequence**: Unannounced corporate action adjustments (spinoffs, rights issues, bonus shares) and irregular dividend timing occasionally introduce minor splicing anomalies compared to authoritative, exchange-cleared NSE Bhavcopy feeds.

### 3. Price-Only Factors (Omission of Fundamentals & Alternative Data)
- **Current Limitation**: The current production model (`model-1.0.json`) is limited to 6 technical and price-derived factors (`mom_12_1`, `mom_6`, `rev_1m`, `vol_6m`, `mdd_12m`, `rel_strength_6m`).
- **Consequence**: Fundamental drivers of corporate earnings quality (e.g. Return on Equity, Debt-to-Equity, Cash Flow Accruals, P/E multiples) and macroeconomic factors (interest rate cycle, crude oil prices) are absent.

### 4. Serial Correlation in Overlapping Labels
- **Current Limitation**: The target variable evaluates forward returns over 126 trading days (~6 calendar months), while portfolios rebalance monthly.
- **Consequence**: Successive monthly test folds share overlapping price trajectories. While our embargo window completely eliminates look-ahead leakage into training data, consecutive out-of-sample test instances exhibit serial correlation. Reported sample sizes ($n=5,332$) reflect individual observation counts rather than statistically independent 6-month blocks.

### 5. Absence of Transaction Costs & Market Impact
- **Current Limitation**: The reported quintile spread (+4.41% 6-month excess return) does not incorporate brokerage commissions, exchange turnover charges, Securities Transaction Tax (STT), slippage, or liquidity constraints.

---

## 2. Roadmap & Future Work

### Phase 2: Point-in-Time Fundamentals Pipeline
- Ingest quarterly financial disclosures (Balance Sheet, Profit & Loss, Cash Flow) from audited BSE/NSE corporate filings.
- Construct point-in-time filing date indexes to prevent look-ahead bias from earnings announcement lags.
- Build fundamental factors: Operating Margin Expansion, Return on Invested Capital (ROIC), Free Cash Flow Yield, and Debt Service Coverage.

### Phase 3: Regulatory Filings & News Ingestion
- Automated RSS scraper for SEBI regulatory announcements, BSE corporate announcements, and audited earnings call transcripts.
- Strict SSRF-hardened fetcher with domain allowlisting, response size limits, and DNS pre-resolution.

### Phase 4: Production LLM Evidence Layer & Prompt Injection Defense
- Wire live Gemini 1.5 Pro / Claude 3.5 Sonnet reasoning agents via OpenAI-compatible endpoints.
- Multi-source citation verifier validating claims against structured regulatory texts before streaming SSE events.
- Implement an automated prompt-injection adversarial test harness (evaluating indirect injection resistance on untrusted filing uploads).

### Phase 5: PDF Research RAG & Vector Store Partitioning
- Vector search layer using ChromaDB / pgvector partitioned strictly per user (`user_id`).
- Chunking and semantic indexing of uploaded annual reports and investor presentations.

### Phase 6: Cloud Deployment & API Gateway
- Containerize FastAPI backend and Vite frontend into multi-stage production Docker images.
- Deploy with Redis-backed distributed rate limiting and automated TLS certificate rotation.
- Optional high-throughput Go API gateway for request routing and token validation.

