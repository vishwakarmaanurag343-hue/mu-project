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
}

export function CalibrationPage(): React.JSX.Element {
  const { data, isLoading } = useQuery<CalibrationData>({
    queryKey: ['calibration'],
    queryFn: () => apiFetch<CalibrationData>('/api/calibration'),
  });

  if (isLoading || !data) {
    return <div className="p-8 text-center text-xs text-slate-500">Loading calibration analytics...</div>;
  }

  // Prepare reliability diagram data comparing forecast to empirical win rate
  const reliabilityData = data.bins.map((b) => ({
    bin: `${(b.bin_center * 100).toFixed(0)}%`,
    ideal: b.bin_center,
    empirical: b.empirical_frequency,
  }));

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Model Calibration & Reliability</h2>
        <p className="text-xs text-slate-500 mt-1">
          Empirical evaluation of predicted outperformance probabilities against historical realized outcomes (Nifty 100).
        </p>
      </div>

      {/* Brier Score Metric Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Overall Brier Score (Mean Squared Error)
          </div>
          <div className="text-3xl font-black text-slate-900 mt-1">
            {data.overall_brier_score.toFixed(3)}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            A score closer to 0 indicates superior calibration (naive coin flip benchmark = 0.250).
          </div>
        </div>
        <div className="text-right text-xs font-medium text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-200">
          Calibrated Engine Active
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Reliability Diagram */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-2">
            Reliability Diagram
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Forecasted probability vs realized empirical outperformance frequency.
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={reliabilityData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bin" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value: number) => `${(Number(value) * 100).toFixed(1)}%`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="ideal"
                  stroke="#94a3b8"
                  strokeDasharray="5 5"
                  name="Perfect Calibration"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="empirical"
                  stroke="#2563eb"
                  strokeWidth={2}
                  name="AlphaLens Model"
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Brier Score Over Time */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-2">
            Brier Score Trajectory
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Longitudinal calibration stability across rolling forward test horizons.
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.brier_history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0.1, 0.25]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="brier_score"
                  stroke="#10b981"
                  strokeWidth={2}
                  name="Rolling Brier Score"
                  dot={{ r: 3 }}
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

