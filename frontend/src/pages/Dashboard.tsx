import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface TickerItem {
  symbol: string;
  name: string;
  sector: string;
}

export function Dashboard(): React.JSX.Element {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // 300ms debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const { data: tickers, isLoading } = useQuery<TickerItem[]>({
    queryKey: ['tickers', debouncedSearch],
    queryFn: () => apiFetch<TickerItem[]>(`/api/tickers?q=${encodeURIComponent(debouncedSearch)}`),
    staleTime: 1000 * 60 * 5,
  });

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 p-6 md:p-12">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-950">AlphaLens</h1>
            <p className="text-slate-600 text-sm mt-1">
              Calibrated, evidence-cited equity research assistant for NSE (India).
            </p>
          </div>
          {user && (
            <div className="flex items-center space-x-4">
              <span className="text-xs text-slate-600 font-mono">{user.email}</span>
              <button
                onClick={() => void logout()}
                className="rounded bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300"
              >
                Sign out
              </button>
            </div>
          )}
        </header>

        {/* Ticker Search Box */}
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-800">Nifty 100 Ticker Search</h2>
          <p className="text-xs text-slate-500 mt-1 mb-4">
            Search historical constituents by NSE symbol (e.g. RELIANCE.NS, TCS.NS) or company name.
          </p>

          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ticker (e.g. RELIANCE, TCS, HDFC)..."
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none shadow-inner"
            />
          </div>

          <div className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
            {isLoading && (
              <div className="p-4 text-center text-xs text-slate-500">Searching universe...</div>
            )}
            {!isLoading && tickers && tickers.length === 0 && (
              <div className="p-4 text-center text-xs text-slate-500">
                No matching constituents found in Nifty 100 universe.
              </div>
            )}
            {tickers &&
              tickers.map((t) => (
                <div
                  key={t.symbol}
                  onClick={() => navigate(`/report/${encodeURIComponent(t.symbol)}`)}
                  className="flex items-center justify-between p-3.5 hover:bg-white cursor-pointer transition-colors"
                >
                  <div>
                    <span className="font-bold text-slate-900 text-sm font-mono mr-2">
                      {t.symbol}
                    </span>
                    <span className="text-xs text-slate-600">{t.name}</span>
                  </div>
                  <span className="text-[11px] font-semibold text-slate-500 bg-slate-200 px-2 py-0.5 rounded">
                    {t.sector}
                  </span>
                </div>
              ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default Dashboard;

