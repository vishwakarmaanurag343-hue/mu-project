import React, { Suspense, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../api/client';
import { QuantTier, type QuantData } from '../components/QuantTier';
import { EvidenceTier } from '../components/EvidenceTier';
import { SkeletonLoader } from '../components/SkeletonLoader';

export function Report(): React.JSX.Element {
  const { ticker } = useParams<{ ticker: string }>();
  const [quantData, setQuantData] = useState<QuantData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;

    setLoading(true);
    setError(null);

    apiFetch<QuantData>(`/api/reports/${encodeURIComponent(ticker)}/quant`)
      .then((data) => {
        setQuantData(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load report');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [ticker]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* Disclaimer Banner */}
      <div className="bg-amber-500 text-slate-950 font-semibold px-4 py-2 text-center text-xs tracking-wide">
        Research and educational purposes only, not investment advice.
      </div>

      <div className="max-w-5xl mx-auto px-4 pt-6 space-y-6">
        {/* Navigation Bar */}
        <div className="flex items-center justify-between">
          <Link
            to="/"
            className="inline-flex items-center text-xs font-semibold text-blue-600 hover:text-blue-800"
          >
            ← Back to Universe Search
          </Link>
          <div className="text-xs text-slate-500 font-mono">Market: NSE India</div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && <SkeletonLoader />}

        {!loading && quantData && (
          <Suspense fallback={<SkeletonLoader />}>
            <QuantTier data={quantData} />
            {ticker && <EvidenceTier ticker={ticker} />}
          </Suspense>
        )}
      </div>
    </div>
  );
}

export default Report;

