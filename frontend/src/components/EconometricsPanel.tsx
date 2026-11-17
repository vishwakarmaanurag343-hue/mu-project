import React from 'react';
import {
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Line,
  ComposedChart,
} from 'recharts';

export interface EconometricData {
  tail_risk: {
    var_95_historical: number;
    var_99_historical: number;
    var_95_cornish_fisher: number;
    cvar_95_expected_shortfall: number;
    skewness: number;
    kurtosis: number;
    jarque_bera_stat: number;
    is_fat_tailed: boolean;
  };
  liquidity: {
    kyles_lambda: number;
    amihud_illiquidity_ratio: number;
    avg_turnover_inr: number;
    liquidity_classification: string;
  };
  regime: {
    current_regime: string;
    regime_confidence: number;
    bull_state_volatility_annual: number;
    bear_state_volatility_annual: number;
    current_annualized_volatility: number;
  };
  distribution_bins?: Array<{
    bin_center: number;
    frequency: number;
    normal_pdf: number;
  }>;
  correlation_matrix?: Array<{
    factor_x: string;
    factor_y: string;
    corr: number;
  }>;
  sharpe_ratio_annual: number;
  sortino_ratio_annual: number;
  max_drawdown_pct: number;
  n_observations: number;
}

interface EconometricsPanelProps {
  data: EconometricData | null;
  loading: boolean;
}

export function EconometricsPanel({ data, loading }: EconometricsPanelProps): React.JSX.Element {
  if (loading) {
    return (
      <div className="rounded-3xl border border-white/10 bg-[#0d1424]/90 p-8 shadow-2xl backdrop-blur-xl animate-pulse text-center text-xs text-slate-400 font-mono">
        <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block mr-2 animate-ping"></span>
        Computing Gaussian Volatility Regimes, Cornish-Fisher VaR & Kyle's Lambda Microstructure...
      </div>
    );
  }

  if (!data) return <div />;

  const isHighVol = data.regime.current_regime === 'HIGH_VOLATILITY_EXPANSION';
  const factors = ['Momentum (21D)', 'Volatility (21D)', 'Illiquidity'];

  const getCorr = (fx: string, fy: string) => {
    const item = data.correlation_matrix?.find(
      (c) => c.factor_x === fx && c.factor_y === fy,
    );
    return item ? item.corr : 1.0;
  };

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#0c1222] via-[#0f172a] to-[#070b14] p-6 lg:p-8 shadow-2xl backdrop-blur-2xl space-y-8">
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-1/3 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-0 left-10 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse"></span>
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-300">
              Quantitative Econometrics & Financial Data Science
            </span>
            <span className="text-[10px] bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 px-2.5 py-0.5 rounded-full font-mono font-bold">
              {data.n_observations} Empirical Sessions Analyzed
            </span>
          </div>
          <h3 className="text-2xl lg:text-3xl font-black text-white mt-1">
            Empirical Return Distribution, Tail Risk & Factor Cross-Correlation
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Non-Gaussian Cornish-Fisher Value-at-Risk, Kyle's Lambda price impact regression, and continuous Gaussian regime dispersion modeling.
          </p>
        </div>

        {/* Academic Benchmark Badge */}
        <div className="bg-[#141d33] border border-white/10 px-4 py-2.5 rounded-2xl text-xs font-mono shadow-inner self-start sm:self-auto">
          <div className="text-[10px] uppercase tracking-wider text-slate-400">Benchmark Hurdle</div>
          <div className="text-sm font-bold text-slate-200 mt-0.5">6.50% (91D T-Bill)</div>
        </div>
      </div>

      {/* Grid 1: 3-Pillar Institutional Quant Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        
        {/* Pillar 1: Volatility Regime Detection */}
        <div className="rounded-2xl border border-white/10 bg-[#0d1424]/90 p-5 space-y-3 shadow-xl">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider font-bold text-slate-400">
              Gaussian Regime Model
            </span>
            <span
              className={`text-[10px] font-black px-2 py-0.5 rounded-full border ${
                isHighVol
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                  : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              }`}
            >
              {data.regime.regime_confidence}% CONFIDENCE
            </span>
          </div>

          <div className="text-lg font-black text-white font-mono mt-1">
            {data.regime.current_regime.replace(/_/g, ' ')}
          </div>

          <div className="space-y-1.5 pt-2 border-t border-white/10 text-xs font-mono">
            <div className="flex justify-between text-slate-400">
              <span>Current Ann. Volatility:</span>
              <span className="text-slate-200 font-bold">{data.regime.current_annualized_volatility}%</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Low-Vol Cluster (Mean):</span>
              <span className="text-emerald-400">{data.regime.bull_state_volatility_annual}%</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>High-Vol Cluster (Mean):</span>
              <span className="text-rose-400">{data.regime.bear_state_volatility_annual}%</span>
            </div>
          </div>
        </div>

        {/* Pillar 2: Value at Risk (VaR) & Cornish-Fisher Tail Loss */}
        <div className="rounded-2xl border border-white/10 bg-[#0d1424]/90 p-5 space-y-3 shadow-xl">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider font-bold text-slate-400">
              Tail Risk & Fat-Tail VaR
            </span>
            <span
              className={`text-[10px] font-black px-2 py-0.5 rounded-full border ${
                data.tail_risk.is_fat_tailed
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-blue-500/20 text-blue-300 border-blue-500/40'
              }`}
            >
              {data.tail_risk.is_fat_tailed ? 'FAT-TAILED (NON-NORMAL)' : 'GAUSSIAN'}
            </span>
          </div>

          <div className="text-lg font-black text-rose-400 font-mono mt-1">
            -{data.tail_risk.cvar_95_expected_shortfall}%
            <span className="text-xs font-normal text-slate-400 ml-1.5">(CVaR 95% Expected Shortfall)</span>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-white/10 text-xs font-mono">
            <div className="flex justify-between text-slate-400">
              <span>Cornish-Fisher VaR (95%):</span>
              <span className="text-rose-400 font-bold">-{data.tail_risk.var_95_cornish_fisher}%</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Historical VaR (99%):</span>
              <span className="text-slate-200">-{data.tail_risk.var_99_historical}%</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Excess Kurtosis / Skew:</span>
              <span className="text-slate-300">{data.tail_risk.kurtosis} / {data.tail_risk.skewness}</span>
            </div>
          </div>
        </div>

        {/* Pillar 3: Microstructure Liquidity & Kyle's Lambda */}
        <div className="rounded-2xl border border-white/10 bg-[#0d1424]/90 p-5 space-y-3 shadow-xl">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider font-bold text-slate-400">
              Kyle's Lambda & Liquidity
            </span>
            <span className="text-[10px] font-black px-2 py-0.5 rounded-full border bg-cyan-500/20 text-cyan-300 border-cyan-500/40">
              {data.liquidity.liquidity_classification}
            </span>
          </div>

          <div className="text-lg font-black text-cyan-400 font-mono mt-1">
            {data.liquidity.kyles_lambda}
            <span className="text-xs font-normal text-slate-400 ml-1.5">(Kyle's λ Impact Parameter)</span>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-white/10 text-xs font-mono">
            <div className="flex justify-between text-slate-400">
              <span>Amihud Illiquidity Ratio:</span>
              <span className="text-slate-200 font-bold">{data.liquidity.amihud_illiquidity_ratio}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Annualized Sharpe Ratio:</span>
              <span className={data.sharpe_ratio_annual >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {data.sharpe_ratio_annual}
              </span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Sortino (Downside) / Max DD:</span>
              <span className="text-slate-300">{data.sortino_ratio_annual} / {data.max_drawdown_pct}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Grid 2: Advanced Visualizations (Return Density Histogram + Factor Covariance Heatmap) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">
        {/* Empirical Return Density Histogram vs Theoretical Normal Distribution */}
        <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-[#0c1222]/90 p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                Empirical Return Distribution vs Theoretical Gaussian PDF
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Observed daily return frequencies (cyan bars) plotted against the ideal normal bell curve (purple curve) proving fat-tail kurtosis.
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            {data.distribution_bins && data.distribution_bins.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={data.distribution_bins}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff" strokeOpacity={0.05} />
                  <XAxis
                    dataKey="bin_center"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: '#64748b', fontSize: 10 }}
                    tickFormatter={(val) => `${val}%`}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: '#64748b', fontSize: 10 }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length && payload[0]?.payload) {
                        const bin = payload[0].payload as {
                          bin_center: number;
                          frequency: number;
                          normal_pdf: number;
                        };
                        return (
                          <div className="rounded-xl border border-white/10 bg-[#090d18]/95 p-3 shadow-xl backdrop-blur-xl text-xs space-y-1">
                            <div className="font-bold text-slate-200">
                              Return Bucket: {bin.bin_center}%
                            </div>
                            <div className="text-cyan-300 font-mono">
                              Observed Count: {bin.frequency} sessions
                            </div>
                            <div className="text-indigo-400 font-mono">
                              Gaussian Expected: {bin.normal_pdf} sessions
                            </div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar dataKey="frequency" fill="#06b6d4" fillOpacity={0.7} radius={[4, 4, 0, 0]} />
                  <Line
                    type="monotone"
                    dataKey="normal_pdf"
                    stroke="#818cf8"
                    strokeWidth={2.5}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                Calculating distribution density...
              </div>
            )}
          </div>
        </div>

        {/* Cross-Factor Covariance & Correlation Heatmap */}
        <div className="rounded-2xl border border-white/10 bg-[#0c1222]/90 p-5 shadow-xl space-y-4">
          <div>
            <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-400"></span>
              Factor Correlation Heatmap
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Empirical Pearson cross-correlation ($r$) across Momentum, Volatility & Illiquidity.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <div className="grid grid-cols-4 gap-1 text-[10px] font-mono font-bold text-slate-400 text-center pb-1 border-b border-white/10">
              <span className="text-left pl-1">Matrix</span>
              <span>MOM</span>
              <span>VOL</span>
              <span>ILLIQ</span>
            </div>

            {factors.map((rowFactor, rIdx) => (
              <div key={rowFactor} className="grid grid-cols-4 gap-1.5 items-center">
                <span className="text-[10px] font-mono text-slate-300 truncate font-semibold">
                  {rIdx === 0 ? 'MOM' : rIdx === 1 ? 'VOL' : 'ILLIQ'}
                </span>
                {factors.map((colFactor) => {
                  const corrVal = getCorr(rowFactor, colFactor);
                  const isDiag = rowFactor === colFactor;
                  const isPositive = corrVal > 0;
                  const intensity = Math.abs(corrVal);

                  let bg = 'bg-slate-800/40 text-slate-300';
                  if (isDiag) {
                    bg = 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-bold';
                  } else if (isPositive) {
                    bg = intensity > 0.3 ? 'bg-emerald-500/30 text-emerald-300' : 'bg-emerald-500/15 text-emerald-400';
                  } else {
                    bg = intensity > 0.3 ? 'bg-rose-500/30 text-rose-300' : 'bg-rose-500/15 text-rose-400';
                  }

                  return (
                    <div
                      key={colFactor}
                      className={`h-9 rounded-lg flex items-center justify-center text-xs font-mono font-bold ${bg} transition-all`}
                    >
                      {corrVal.toFixed(2)}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-white/10 flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Range: -1.0 (Inverse) to +1.0 (Aligned)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
export default EconometricsPanel;
