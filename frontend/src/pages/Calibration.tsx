import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface CalibrationBin {
  bin_center: number;
  predicted_avg: number;
  empirical_frequency: number;
  sample_count: number;
}

interface BrierPoint {
  date: string;
  brier_score: number;
}

interface CalibrationData {
  bins: CalibrationBin[];
  brier_history: BrierPoint[];
  overall_brier_score: number;
  baseline_brier_score: number;
  brier_skill_score: number;
  coin_flip_brier_score: number;
}

export function CalibrationPage(): React.JSX.Element {
  const { data, isLoading } = useQuery<CalibrationData>({
    queryKey: ['calibration'],
    queryFn: () => apiFetch<CalibrationData>('/api/calibration'),
  });

  if (isLoading || !data) {
    return <div className="p-8 text-center text-xs text-slate-400">Loading calibration analytics...</div>;
  }

  // Prepare reliability diagram data comparing forecast to empirical win rate
  const reliabilityData = data.bins.map((b) => ({
    bin: `${(b.bin_center * 100).toFixed(0)}%`,
    ideal: b.bin_center,
    empirical: b.empirical_frequency,
  }));

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 p-6 md:p-10 space-y-8 max-w-6xl mx-auto">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#121c33] via-[#0e1628] to-[#12182b] border border-white/10 p-8 shadow-2xl">
        <h1 className="text-3xl font-black text-white tracking-tight">
          AlphaLens Reliability & Calibration Lab
        </h1>
        <p className="text-slate-400 text-sm mt-2 max-w-2xl leading-relaxed">
          Empirical walk-forward calibration curves, Brier skill evolution over time, and statistical score diagnostics across all 119 monthly rebalance folds.
        </p>
      </div>

      {/* Summary Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-white/10 bg-[#0d1322]/90 p-5 backdrop-blur-xl">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Model Brier Score</div>
          <div className="text-3xl font-black text-white mt-1">
            {data.overall_brier_score.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Lower is better</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d1322]/90 p-5 backdrop-blur-xl">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Base Rate Baseline</div>
          <div className="text-3xl font-black text-slate-300 mt-1">
            {data.baseline_brier_score.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Trailing historical rate</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d1322]/90 p-5 backdrop-blur-xl">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Brier Skill Score (BSS)</div>
          <div className="text-3xl font-black text-cyan-400 mt-1">
            {data.brier_skill_score >= 0
              ? `+${data.brier_skill_score.toFixed(4)}`
              : data.brier_skill_score.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">≈ 0.0 (Relative rank signal)</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d1322]/90 p-5 backdrop-blur-xl">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Evaluated Samples</div>
          <div className="text-3xl font-black text-emerald-400 mt-1">5,332</div>
          <div className="text-[10px] text-slate-500 mt-1">Common out-of-sample folds</div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reliability Curve */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 p-6 lg:p-8 backdrop-blur-xl shadow-2xl">
          <h3 className="text-sm font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            Empirical Reliability Diagram (10 Bins)
          </h3>
          <p className="text-xs text-slate-400 mb-6">
            Mean predicted probability vs observed empirical outperformance win-rate.
          </p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={reliabilityData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="bin" stroke="#94a3b8" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11, fill: '#94a3b8' }} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0d1322',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Line
                  type="monotone"
                  dataKey="ideal"
                  stroke="#64748b"
                  strokeDasharray="4 4"
                  name="Perfect Calibration"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="empirical"
                  stroke="#06b6d4"
                  strokeWidth={2.5}
                  name="Model (bt-1.0)"
                  dot={{ r: 4, fill: '#06b6d4' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Brier Score Over Time */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 p-6 lg:p-8 backdrop-blur-xl shadow-2xl">
          <h3 className="text-sm font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400"></span>
            Brier Score Trajectory Over Time
          </h3>
          <p className="text-xs text-slate-400 mb-6">
            Trailing fold-by-fold Brier score progression across 2017–2026 out-of-sample window.
          </p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.brier_history} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11, fill: '#94a3b8' }} domain={[0, 0.5]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0d1322',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="brier_score"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  name="Brier Score"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CalibrationPage;
