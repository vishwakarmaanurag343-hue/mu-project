import React from 'react';
import { FactorChart } from './FactorChart';
import { StockPriceChart, type ChartCandle } from './StockPriceChart';

export interface QuantData {
  ticker: string;
  probability: number;
  confidence_interval: {
    lower: number;
    upper: number;
  };
  decision_label: string;
  as_of: string;
  factor_contributions: Array<{
    factor: string;
    contribution: number;
    score: number;
  }>;
  scenarios: Record<
    string,
    {
      return_pct: number;
      description: string;
    }
  >;
  model_version: string;
}

export interface LiveQuoteData {
  ticker: string;
  last_price: number | null;
  previous_close: number | null;
  change_pct: number | null;
  day_high: number | null;
  day_low: number | null;
  market_cap?: number | null;
  currency: string;
  is_live: boolean;
  history?: ChartCandle[];
}

export function QuantTier({
  data,
  liveQuote,
}: {
  data: QuantData;
  liveQuote?: LiveQuoteData | null;
}): React.JSX.Element {
  const probPercent = (data.probability * 100).toFixed(1);
  const lowerPercent = (data.confidence_interval.lower * 100).toFixed(1);
  const upperPercent = (data.confidence_interval.upper * 100).toFixed(1);

  const badgeColor =
    data.decision_label.startsWith('Top quintile')
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
      : data.decision_label === 'Bottom quintile'
        ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
        : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

  return (
    <div className="space-y-6">
      {/* 1. Primary Market Price & Candlestick/Area Terminal Chart */}
      <StockPriceChart
        ticker={data.ticker}
        history={liveQuote?.history}
        currentPrice={liveQuote?.last_price}
        changePct={liveQuote?.change_pct}
        marketCap={liveQuote?.market_cap}
        dayHigh={liveQuote?.day_high}
        dayLow={liveQuote?.day_low}
      />

      {/* 2. AlphaLens Probability Gauge & Model Overview */}
      <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#0e1628] via-[#121c33] to-[#0b101d] p-7 shadow-2xl flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 backdrop-blur-xl">
        <div className="absolute top-0 right-1/4 w-72 h-72 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl lg:text-3xl font-black text-white tracking-tight">
              {data.ticker}
            </h2>
            <span
              className={`rounded-full border px-3.5 py-1 text-xs font-bold uppercase tracking-wider ${badgeColor}`}
            >
              {data.decision_label}
            </span>
            {liveQuote?.is_live && (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Live Feed Active</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 flex flex-wrap items-center gap-2 font-mono">
            <span>
              As of: <span className="text-slate-200 font-semibold">{data.as_of}</span>
            </span>
            <span>·</span>
            <span>Horizon: 6 Months (126d)</span>
            <span>·</span>
            <span>
              Engine: <span className="text-cyan-400 font-bold">model-{data.model_version}</span>
            </span>
          </p>
        </div>

        {/* Probability & Calibration Callout Card */}
        <div className="relative z-10 flex flex-col items-start lg:items-end gap-2 w-full lg:w-auto">
          <div className="bg-[#152039]/80 backdrop-blur-md rounded-2xl p-4 border border-white/10 flex items-center gap-6 shadow-xl w-full lg:w-auto justify-between lg:justify-start">
            <div>
              <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
                Outperformance Probability
              </div>
              <div className="text-3xl lg:text-4xl font-black bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-300 bg-clip-text text-transparent mt-0.5">
                {probPercent}%
              </div>
            </div>
            <div className="text-xs text-slate-400 border-l border-white/10 pl-5">
              <div className="text-[10px] uppercase font-semibold text-slate-400">Confidence Band</div>
              <div className="text-base font-bold text-slate-200 mt-0.5">
                {lowerPercent}% – {upperPercent}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">P(6M TR &gt; Nifty 50 TRI)</div>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 max-w-sm text-left lg:text-right leading-tight italic">
            Backtest shows ranking signal but no calibration skill beyond the base rate; treat the probability as a relative score.
          </p>
        </div>
      </div>

      {/* 3. Factors and Scenarios Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Factor Attribution */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-6 lg:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
              Factor Attribution (6-Month Horizon)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mb-6">
            Precomputed factor score contributions ($z \times \beta$) relative to Nifty 50 historical cross-section.
          </p>
          <FactorChart factors={data.factor_contributions} />
        </div>

        {/* 6-Month Return Scenarios */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-6 lg:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              Bootstrapped Scenario Expectations
            </h3>
          </div>
          <p className="text-xs text-slate-400 mb-6">
            10,000-path Monte Carlo forward return distributions bootstrapped over 3-year historical volatility.
          </p>
          <div className="space-y-3.5">
            {Object.entries(data.scenarios).map(([key, item]) => {
              const isBull = key === 'bull';
              const isBear = key === 'bear';
              const cardColor = isBull
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                : isBear
                  ? 'bg-rose-500/10 border-rose-500/20 text-rose-300'
                  : 'bg-blue-500/10 border-blue-500/20 text-blue-300';

              return (
                <div key={key} className={`rounded-2xl border p-4 backdrop-blur-md ${cardColor}`}>
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider">
                    <span className="font-bold flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isBull ? 'bg-emerald-400' : isBear ? 'bg-rose-400' : 'bg-blue-400'
                        }`}
                      ></span>
                      {key} Case
                    </span>
                    <span className="text-base font-black font-mono">
                      {item.return_pct > 0 ? `+${item.return_pct}%` : `${item.return_pct}%`}
                    </span>
                  </div>
                  <p className="text-xs mt-1.5 leading-relaxed opacity-90 text-slate-300">
                    {item.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
