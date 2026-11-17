import React, { Suspense, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../api/client';
import { QuantTier, type QuantData } from '../components/QuantTier';
import { EvidenceTier } from '../components/EvidenceTier';
import { SkeletonLoader } from '../components/SkeletonLoader';
import { MicrostructureTerminal } from '../components/MicrostructureTerminal';
import { EconometricsPanel, type EconometricData } from '../components/EconometricsPanel';

export interface LiveQuote {
  ticker: string;
  last_price: number | null;
  previous_close: number | null;
  change_pct: number | null;
  day_high: number | null;
  day_low: number | null;
  market_cap?: number | null;
  currency: string;
  is_live: boolean;
  history?: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

export function Report(): React.JSX.Element {
  const { ticker } = useParams<{ ticker: string }>();
  const [quantData, setQuantData] = useState<QuantData | null>(null);
  const [liveQuote, setLiveQuote] = useState<LiveQuote | null>(null);
  const [econometrics, setEconometrics] = useState<EconometricData | null>(null);
  const [loadingEcon, setLoadingEcon] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;

    setLoading(true);
    setLoadingEcon(true);
    setError(null);

    // 1. Fetch precomputed quant metrics
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

    // 2. Fetch live market price from Yahoo Finance
    apiFetch<LiveQuote>(`/api/reports/${encodeURIComponent(ticker)}/live-quote`)
      .then((quote) => {
        setLiveQuote(quote);
      })
      .catch(() => {
        setLiveQuote(null);
      });

    // 3. Fetch live econometric calculations
    apiFetch<EconometricData>(`/api/reports/${encodeURIComponent(ticker)}/econometrics`)
      .then((econ) => {
        setEconometrics(econ);
      })
      .catch(() => {
        setEconometrics(null);
      })
      .finally(() => {
        setLoadingEcon(false);
      });
  }, [ticker]);

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 pb-16">
      {/* Top Disclaimer Badge */}
      <div className="bg-gradient-to-r from-blue-900/40 via-amber-500/20 to-blue-900/40 border-b border-amber-500/20 text-amber-300 font-semibold px-4 py-2 text-center text-xs tracking-wide backdrop-blur-md">
        Research and educational purposes only, not investment advice.
      </div>

      <div className="max-w-6xl mx-auto px-4 pt-6 space-y-6">
        {/* Navigation Bar */}
        <div className="flex items-center justify-between">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition-colors bg-[#0e1628] border border-white/10 px-3.5 py-1.5 rounded-xl shadow-sm"
          >
            ← Back to Universe Search
          </Link>
          <div className="text-xs text-slate-400 font-mono flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            Market: National Stock Exchange (NSE India)
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-950/40 p-5 text-sm text-red-300 backdrop-blur-md">
            {error}
          </div>
        )}

        {loading && <SkeletonLoader />}

        {!loading && quantData && (
          <Suspense fallback={<SkeletonLoader />}>
            <MicrostructureTerminal />
            <QuantTier data={quantData} liveQuote={liveQuote} />
            <EconometricsPanel data={econometrics} loading={loadingEcon} />
            {ticker && <EvidenceTier ticker={ticker} />}
          </Suspense>
        )}
      </div>
    </div>
  );
}

export default Report;

