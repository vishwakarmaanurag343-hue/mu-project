import React from 'react';
import { FactorChart } from './FactorChart';

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

export function QuantTier({ data }: { data: QuantData }): React.JSX.Element {
  const probPercent = (data.probability * 100).toFixed(1);
  const lowerPercent = (data.confidence_interval.lower * 100).toFixed(1);
  const upperPercent = (data.confidence_interval.upper * 100).toFixed(1);

  const badgeColor =
    data.decision_label === 'Overweight'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
      : data.decision_label === 'Underweight'
        ? 'bg-rose-100 text-rose-800 border-rose-300'
        : 'bg-amber-100 text-amber-800 border-amber-300';

  return (
    <div className="space-y-6">
      {/* Probability Gauge & Overview Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-extrabold text-slate-900">{data.ticker}</h2>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${badgeColor}`}
            >
              {data.decision_label}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            As of: <span className="font-medium text-slate-700">{data.as_of}</span> · Model horizon: 6 months · Quant Engine:{' '}
            <span className="font-mono">{data.model_version}</span>
          </p>
        </div>

        <div className="bg-slate-50 rounded-lg p-4 border border-slate-100 flex items-baseline gap-4">
          <div>
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">
              Outperformance Probability
            </div>
            <div className="text-4xl font-black text-slate-900">
              {probPercent}%
            </div>
          </div>
          <div className="text-xs text-slate-500 border-l border-slate-200 pl-3">
            <div>Confidence Band:</div>
            <div className="font-semibold text-slate-700">
              {lowerPercent}% – {upperPercent}%
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">P(6M Return &gt; Nifty 50)</div>
          </div>
        </div>
      </div>

      {/* Factors and Scenarios Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Factor Attribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-2">
            Factor Attribution (6-Month Horizon)
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Precomputed factor score contributions relative to Nifty 100 historical universe.
          </p>
          <FactorChart factors={data.factor_contributions} />
        </div>

        {/* 6-Month Return Scenarios */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-2">
            Scenario Expectations
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Conditional forward return projections derived from quantitative regime clustering.
          </p>
          <div className="space-y-3">
            {Object.entries(data.scenarios).map(([key, item]) => {
              const isBull = key === 'bull';
              const isBear = key === 'bear';
              const color = isBull
                ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                : isBear
                  ? 'text-rose-700 bg-rose-50 border-rose-200'
                  : 'text-slate-700 bg-slate-50 border-slate-200';

              return (
                <div key={key} className={`rounded-lg border p-3 ${color}`}>
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider">
                    <span>{key} Scenario</span>
                    <span className="text-sm font-bold">
                      {item.return_pct > 0 ? `+${item.return_pct}%` : `${item.return_pct}%`}
                    </span>
                  </div>
                  <p className="text-xs mt-1 leading-relaxed opacity-90">{item.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
