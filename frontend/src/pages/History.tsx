import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { Link } from 'react-router-dom';

interface HistoryRecord {
  id: string;
  ticker: string;
  probability: number;
  decision_label: string;
  model_version: string;
  outcome: number | null;
  model_horizon_months: number;
  created_at: string;
}

export function HistoryPage(): React.JSX.Element {
  const { data: history, isLoading } = useQuery<HistoryRecord[]>({
    queryKey: ['history'],
    queryFn: () => apiFetch<HistoryRecord[]>('/api/history?limit=50'),
  });

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-8 shadow-2xl space-y-6">
          <div className="border-b border-white/5 pb-4">
            <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
              Your Prediction Audit History
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Append-only audit trail of quantitative queries, factor snapshots, and realized forward outcomes.
            </p>
          </div>

          {isLoading && <p className="text-xs text-slate-400">Loading history records...</p>}

          {history && history.length === 0 && (
            <p className="text-xs text-slate-400">No predictions recorded yet. Run a report to begin.</p>
          )}

          {history && history.length > 0 && (
            <div className="border border-white/10 rounded-2xl overflow-x-auto bg-[#121829]/60">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#18233d]/80 border-b border-white/10 text-slate-300 font-bold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="p-3.5">Date</th>
                    <th className="p-3.5">Ticker</th>
                    <th className="p-3.5">P(Outperform)</th>
                    <th className="p-3.5">Decision</th>
                    <th className="p-3.5">Horizon</th>
                    <th className="p-3.5">Model</th>
                    <th className="p-3.5">Outcome</th>
                    <th className="p-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {history.map((item) => (
                    <tr key={item.id} className="hover:bg-white/5 transition-colors">
                      <td className="p-3.5 text-slate-400 font-mono text-[11px]">
                        {new Date(item.created_at).toLocaleDateString()}
                      </td>
                      <td className="p-3.5 font-bold font-mono text-cyan-400">{item.ticker}</td>
                      <td className="p-3.5 font-bold text-white">
                        {(item.probability * 100).toFixed(1)}%
                      </td>
                      <td className="p-3.5">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                            item.decision_label.startsWith('Top quintile') || item.decision_label === 'Overweight'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : item.decision_label === 'Bottom quintile' || item.decision_label === 'Underweight'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                                : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                          }`}
                        >
                          {item.decision_label}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-300 font-medium text-[11px]">
                        Model horizon: 6 months
                      </td>
                      <td className="p-3.5 font-mono text-slate-400 text-[11px]">{item.model_version}</td>
                      <td className="p-3.5 text-slate-300">
                        {item.outcome !== null ? (
                          <span className="font-semibold text-emerald-400">
                            {item.outcome > 0 ? `+${item.outcome}%` : `${item.outcome}%`}
                          </span>
                        ) : (
                          <span className="text-slate-500 italic">Pending (6M)</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right">
                        <Link
                          to={`/report/${encodeURIComponent(item.ticker)}`}
                          className="text-cyan-400 font-medium hover:underline hover:text-cyan-300"
                        >
                          View Report →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HistoryPage;
