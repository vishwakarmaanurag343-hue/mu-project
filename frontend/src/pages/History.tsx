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
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-slate-900">Your Prediction History</h2>
        <p className="text-xs text-slate-500 mt-1 mb-4">
          Append-only personal audit log of quantitative research queries and realized outcomes.
        </p>

        {isLoading && <p className="text-xs text-slate-500">Loading history...</p>}

        {history && history.length === 0 && (
          <p className="text-xs text-slate-500">No predictions recorded yet. Run a report to begin.</p>
        )}

        {history && history.length > 0 && (
          <div className="border border-slate-200 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="p-3">Date</th>
                  <th className="p-3">Ticker</th>
                  <th className="p-3">P(Outperform)</th>
                  <th className="p-3">Decision</th>
                  <th className="p-3">Horizon</th>
                  <th className="p-3">Model</th>
                  <th className="p-3">Outcome</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                    <td className="p-3 text-slate-500 font-mono">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-3 font-bold font-mono text-slate-900">{item.ticker}</td>
                    <td className="p-3 font-semibold text-slate-800">
                      {(item.probability * 100).toFixed(1)}%
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          item.decision_label === 'Overweight'
                            ? 'bg-emerald-100 text-emerald-800'
                            : item.decision_label === 'Underweight'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {item.decision_label}
                      </span>
                    </td>
                    <td className="p-3 text-slate-600 font-medium text-[11px]">
                      Model horizon: 6 months
                    </td>
                    <td className="p-3 font-mono text-slate-500 text-[11px]">{item.model_version}</td>
                    <td className="p-3 text-slate-600">
                      {item.outcome !== null ? (
                        <span className="font-semibold">{item.outcome > 0 ? `+${item.outcome}%` : `${item.outcome}%`}</span>
                      ) : (
                        <span className="text-slate-400 italic">Pending (6M)</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <Link
                        to={`/report/${encodeURIComponent(item.ticker)}`}
                        className="text-blue-600 font-medium hover:underline"
                      >
                        View
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
  );
}

export default HistoryPage;
