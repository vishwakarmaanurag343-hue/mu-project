import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';

interface TickerItem {
  symbol: string;
  name: string;
  sector: string;
}

// Major indices & market summary mock benchmarks for the terminal ticker tape
const MARKET_INDICES = [
  { name: 'NIFTY 50', value: '24,367.50', change: '+128.40', pct: '+0.53%', isUp: true },
  { name: 'SENSEX', value: '80,248.10', change: '+384.25', pct: '+0.48%', isUp: true },
  { name: 'BANK NIFTY', value: '51,890.30', change: '-112.10', pct: '-0.22%', isUp: false },
  { name: 'NIFTY IT', value: '42,150.80', change: '+490.65', pct: '+1.18%', isUp: true },
  { name: 'INDIA VIX', value: '14.28', change: '-0.62', pct: '-4.16%', isUp: false },
];

const POPULAR_WATCHLIST = [
  { symbol: 'RELIANCE.NS', name: 'Reliance Industries', price: '₹1,274.50', change: '+1.42%', isUp: true, sector: 'Energy' },
  { symbol: 'TCS.NS', name: 'Tata Consultancy Services', price: '₹4,120.00', change: '+0.85%', isUp: true, sector: 'IT' },
  { symbol: 'HDFCBANK.NS', name: 'HDFC Bank', price: '₹1,745.20', change: '-0.38%', isUp: false, sector: 'Banking' },
  { symbol: 'INFY.NS', name: 'Infosys', price: '₹1,860.00', change: '+2.10%', isUp: true, sector: 'IT' },
  { symbol: 'ICICIBANK.NS', name: 'ICICI Bank', price: '₹1,268.40', change: '+0.60%', isUp: true, sector: 'Banking' },
  { symbol: 'ADANIENT.NS', name: 'Adani Enterprises', price: '₹2,840.10', change: '-1.15%', isUp: false, sector: 'Metals' },
];

export function Dashboard(): React.JSX.Element {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedSector, setSelectedSector] = useState<string>('ALL');
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

  const sectors = ['ALL', 'Financial Services', 'Information Technology', 'Energy', 'Fast Moving Consumer Goods', 'Automobile'];

  const filteredTickers = (tickers || []).filter((t) => {
    if (selectedSector === 'ALL') return true;
    return t.sector.toLowerCase().includes(selectedSector.toLowerCase());
  });

  return (
    <main className="min-h-screen bg-[#070b12] text-slate-100 p-4 md:p-8 space-y-6">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* 1. Live Market Ticker Tape */}
        <div className="flex items-center gap-4 overflow-x-auto py-2.5 px-4 bg-[#0a0f1d] border border-white/5 rounded-2xl scrollbar-none shadow-inner">
          <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-cyan-400 shrink-0 pr-3 border-r border-white/10">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Live Market
          </div>
          <div className="flex items-center gap-6 min-w-max">
            {MARKET_INDICES.map((idx) => (
              <div key={idx.name} className="flex items-center gap-2 text-xs font-mono">
                <span className="text-slate-400 font-semibold">{idx.name}</span>
                <span className="text-slate-100 font-bold">{idx.value}</span>
                <span
                  className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
                    idx.isUp ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
                  }`}
                >
                  {idx.pct}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 2. Terminal Header & Market Overview Hero Card */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0e1628] via-[#121c33] to-[#090e1a] border border-white/10 p-6 md:p-8 shadow-2xl backdrop-blur-xl">
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-semibold uppercase tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                Quantitative Research Terminal · NSE Universe
              </div>
              <h1 className="text-3xl md:text-4xl font-black tracking-tight text-white">
                AlphaLens Market Radar
              </h1>
              <p className="text-slate-400 text-xs md:text-sm max-w-xl leading-relaxed">
                Walk-forward calibrated outperformance forecasting, cross-sectional factor exposure, and multi-scenario Monte Carlo simulations for Indian equities.
              </p>
            </div>

            {/* Quick Metrics Badges */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full lg:w-auto">
              <div className="bg-[#152039]/80 backdrop-blur-md rounded-2xl border border-white/10 p-3.5 shadow-xl">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Universe Benchmark</div>
                <div className="text-base font-bold text-white mt-0.5">Nifty 50 TRI</div>
                <div className="text-[10px] text-emerald-400 mt-0.5 font-mono">100% Point-in-time</div>
              </div>
              <div className="bg-[#152039]/80 backdrop-blur-md rounded-2xl border border-white/10 p-3.5 shadow-xl">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Forecast Horizon</div>
                <div className="text-base font-bold text-cyan-400 mt-0.5">6 Months</div>
                <div className="text-[10px] text-slate-400 mt-0.5 font-mono">126 trading days</div>
              </div>
              <div className="bg-[#152039]/80 backdrop-blur-md rounded-2xl border border-white/10 p-3.5 shadow-xl col-span-2 sm:col-span-1">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Quant Engine</div>
                <div className="text-base font-bold text-indigo-300 mt-0.5">Ridge / Walk-Fwd</div>
                <div className="text-[10px] text-cyan-400 mt-0.5 font-mono">BSS-Calibrated</div>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Market Watchlist Grid (High-Profile Equities) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
              Trending Constituents & Market Prices
            </h2>
            <span className="text-[11px] text-slate-500 font-mono">Click any ticker to open analysis</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {POPULAR_WATCHLIST.map((item) => (
              <div
                key={item.symbol}
                onClick={() => navigate(`/report/${encodeURIComponent(item.symbol)}`)}
                className="group cursor-pointer rounded-2xl border border-white/10 bg-[#0d1424]/90 p-3.5 hover:border-cyan-500/40 hover:bg-[#121c33] transition-all shadow-lg flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white font-mono group-hover:text-cyan-400 transition-colors">
                      {item.symbol.replace('.NS', '')}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        item.isUp ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
                      }`}
                    >
                      {item.change}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate mt-0.5">{item.name}</div>
                </div>

                <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200 font-mono">{item.price}</span>
                  <span className="text-[10px] text-slate-500 font-medium">{item.sector}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 4. Interactive Stock Screener & Ticker Universe Table */}
        <section className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-6 md:p-8 shadow-2xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>NSE Equity Screener & Valuation Terminal</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Filter constituents across sectors or search ticker symbols for detailed quantitative factor exposure and risk decomposition.
              </p>
            </div>

            {/* Sector Quick-Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
              {sectors.map((sec) => (
                <button
                  key={sec}
                  onClick={() => setSelectedSector(sec)}
                  className={`px-3 py-1 text-xs font-semibold rounded-xl whitespace-nowrap transition-all ${
                    selectedSector === sec
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
                  }`}
                >
                  {sec === 'ALL' ? 'All Sectors' : sec}
                </button>
              ))}
            </div>
          </div>

          {/* Search Input Bar */}
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ticker or company (e.g. RELIANCE, TCS, INFY, ADANIENT)..."
              className="w-full rounded-2xl border border-white/10 bg-[#141d33] pl-11 pr-5 py-3.5 text-sm text-white placeholder-slate-500 focus:border-cyan-500/50 focus:bg-[#18233d] focus:outline-none focus:ring-4 focus:ring-cyan-500/10 transition-all shadow-inner"
            />
          </div>

          {/* Constituents Grid / Table */}
          <div className="rounded-2xl border border-white/5 bg-[#10172a]/70 overflow-hidden divide-y divide-white/5">
            {isLoading && (
              <div className="p-8 text-center text-xs text-slate-400 animate-pulse flex items-center justify-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                Scanning equity universe...
              </div>
            )}
            {!isLoading && filteredTickers.length === 0 && (
              <div className="p-8 text-center text-xs text-slate-400">
                No matching constituents found for "{search}" in {selectedSector === 'ALL' ? 'Nifty 50' : selectedSector}.
              </div>
            )}
            {filteredTickers.map((t) => (
              <div
                key={t.symbol}
                onClick={() => navigate(`/report/${encodeURIComponent(t.symbol)}`)}
                className="flex items-center justify-between p-4 hover:bg-gradient-to-r hover:from-cyan-500/10 hover:to-transparent cursor-pointer transition-all group"
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-[#1b2642] border border-white/10 flex items-center justify-center font-bold text-xs text-cyan-400 group-hover:scale-105 group-hover:border-cyan-500/40 transition-all shadow-sm">
                    {t.symbol.replace('.NS', '').slice(0, 3)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm font-mono group-hover:text-cyan-400 transition-colors">
                        {t.symbol}
                      </span>
                      <span className="text-[10px] text-slate-400 bg-white/5 px-2 py-0.5 rounded font-mono">
                        NSE
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">{t.name}</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-semibold text-slate-300 bg-white/5 border border-white/10 px-3 py-1 rounded-full hidden sm:inline-block">
                    {t.sector}
                  </span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 group-hover:translate-x-1 transition-transform">
                    <span>Inspect</span>
                    <span>→</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default Dashboard;
