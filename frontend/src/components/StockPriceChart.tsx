import React, { useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

export interface ChartCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockPriceChartProps {
  ticker: string;
  history?: ChartCandle[];
  currentPrice?: number | null;
  changePct?: number | null;
  marketCap?: number | null;
  dayHigh?: number | null;
  dayLow?: number | null;
}

export function StockPriceChart({
  ticker,
  history,
  currentPrice,
  changePct,
  marketCap,
  dayHigh,
  dayLow,
}: StockPriceChartProps): React.JSX.Element {
  const [timeRange, setTimeRange] = useState<'1W' | '1M' | 'ALL'>('1M');
  const [chartMode, setChartMode] = useState<'candles' | 'line'>('candles');
  const [hoveredCandle, setHoveredCandle] = useState<ChartCandle | null>(null);

  // Filter history based on timeRange
  const data = React.useMemo(() => {
    if (!history || history.length === 0) return [];
    if (timeRange === '1W') {
      return history.slice(-7);
    }
    if (timeRange === '1M') {
      return history.slice(-22);
    }
    return history;
  }, [history, timeRange]);

  const isPositive = (changePct ?? 0) >= 0;
  const strokeColor = isPositive ? '#10b981' : '#f43f5e';
  const gradientColor = isPositive ? '#10b981' : '#f43f5e';

  // Calculate volume summary
  const lastCandle = data.length > 0 ? data[data.length - 1] : null;
  const avgVolume = React.useMemo(() => {
    if (!data.length) return 0;
    const sum = data.reduce((acc, c) => acc + (c.volume || 0), 0);
    return Math.round(sum / data.length);
  }, [data]);

  const formatLargeNum = (num?: number | null) => {
    if (!num) return '—';
    if (num >= 1e12) return `₹${(num / 1e12).toFixed(2)} T`;
    if (num >= 1e9) return `₹${(num / 1e9).toFixed(2)} B`;
    if (num >= 1e7) return `₹${(num / 1e7).toFixed(2)} Cr`;
    if (num >= 1e5) return `₹${(num / 1e5).toFixed(2)} L`;
    return `₹${num.toLocaleString('en-IN')}`;
  };

  const formatVolume = (vol: number) => {
    if (vol >= 1e6) return `${(vol / 1e6).toFixed(2)} M`;
    if (vol >= 1e3) return `${(vol / 1e3).toFixed(1)} K`;
    return vol.toString();
  };

  // Find price bounds for true SVG scaling
  const { minPrice, maxPrice, priceRange } = React.useMemo(() => {
    if (!data.length) return { minPrice: 0, maxPrice: 100, priceRange: 100 };
    const min = Math.min(...data.map((d) => d.low));
    const max = Math.max(...data.map((d) => d.high));
    const pad = (max - min) * 0.08 || 10;
    return {
      minPrice: min - pad,
      maxPrice: max + pad,
      priceRange: max + pad - (min - pad),
    };
  }, [data]);

  // Price ticks for background grid
  const yTicks = React.useMemo(() => {
    if (!data.length) return [];
    const step = priceRange / 4;
    return [0, 1, 2, 3, 4].map((i) => Math.round(minPrice + step * i));
  }, [minPrice, priceRange, data.length]);

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#0c1222] via-[#0f172a] to-[#070b14] p-6 lg:p-8 shadow-2xl backdrop-blur-2xl">
      {/* Background ambient radial glow */}
      <div className="absolute top-0 right-1/3 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* Top Bar: Price, Change %, Chart Style Selector, Timeframe Pills */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/5">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-3xl lg:text-5xl font-black text-white tracking-tight font-mono">
              {currentPrice !== null && currentPrice !== undefined
                ? `₹${currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : '₹—'}
            </span>
            {changePct !== null && changePct !== undefined && (
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-black font-mono shadow-lg ${
                  isPositive
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                }`}
              >
                {isPositive ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-xs text-slate-400 font-medium">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50"></span>
            <span className="text-slate-100 font-bold tracking-wide">{ticker}</span>
            <span>·</span>
            <span className="text-slate-400">National Stock Exchange of India (NSE)</span>
            <span className="ml-1 text-[10px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold">
              Live Feed
            </span>
          </div>
        </div>

        {/* View Mode (Candles vs Area) & Timeframe Selector Pills */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Chart mode toggle */}
          <div className="flex items-center gap-1 bg-[#090d18]/80 p-1 rounded-xl border border-white/10">
            <button
              onClick={() => setChartMode('candles')}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
                chartMode === 'candles'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🕯️</span>
              <span>Candles</span>
            </button>
            <button
              onClick={() => setChartMode('line')}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
                chartMode === 'line'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>📈</span>
              <span>Line</span>
            </button>
          </div>

          {/* Timeframe pills */}
          <div className="flex items-center gap-1 bg-[#090d18]/80 p-1 rounded-xl border border-white/10">
            {(['1W', '1M', 'ALL'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                  timeRange === range
                    ? 'bg-blue-600/30 text-white border border-blue-400/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Terminal Grid: Side Stats Column + Candlestick/Line Canvas */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-5 gap-6 pt-6">
        {/* Left Side Stats */}
        <div className="lg:col-span-1 grid grid-cols-2 lg:grid-cols-1 gap-3.5">
          <div className="bg-[#0b1222]/90 border border-white/10 rounded-2xl p-4 shadow-lg backdrop-blur-md">
            <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
              Market Capitalization
            </div>
            <div className="text-base lg:text-lg font-black text-slate-100 mt-1 font-mono">
              {formatLargeNum(marketCap)}
            </div>
          </div>

          <div className="bg-[#0b1222]/90 border border-white/10 rounded-2xl p-4 shadow-lg backdrop-blur-md">
            <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
              Avg Daily Volume
            </div>
            <div className="text-base lg:text-lg font-black text-slate-100 mt-1 font-mono">
              {formatVolume(avgVolume)}
            </div>
          </div>

          <div className="bg-[#0b1222]/90 border border-white/10 rounded-2xl p-4 shadow-lg backdrop-blur-md">
            <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
              Latest Session Volume
            </div>
            <div className="text-base lg:text-lg font-black text-cyan-400 mt-1 font-mono">
              {lastCandle ? formatVolume(lastCandle.volume) : '—'}
            </div>
          </div>

          {(dayHigh || dayLow) && (
            <div className="bg-[#0b1222]/90 border border-white/10 rounded-2xl p-4 shadow-lg backdrop-blur-md">
              <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
                24h Day Range
              </div>
              <div className="text-xs font-bold text-slate-200 mt-1 font-mono">
                ₹{dayLow ?? '—'} – ₹{dayHigh ?? '—'}
              </div>
            </div>
          )}
        </div>

        {/* Right Area: True Candlestick / Line Chart */}
        <div className="lg:col-span-4 h-80 w-full relative">
          {data.length > 0 ? (
            chartMode === 'candles' ? (
              /* High-Fidelity Custom SVG Candlestick Chart */
              <div className="w-full h-full relative select-none">
                {/* Floating Tooltip if hovering a candle */}
                {hoveredCandle && (
                  <div className="absolute top-2 right-4 z-20 rounded-2xl border border-white/10 bg-[#090d18]/95 p-3.5 shadow-2xl backdrop-blur-xl text-xs space-y-1.5 pointer-events-none">
                    <div className="flex items-center justify-between border-b border-white/10 pb-1 font-bold">
                      <span className="text-slate-200">{hoveredCandle.date}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                          hoveredCandle.close >= hoveredCandle.open
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-rose-500/20 text-rose-400'
                        }`}
                      >
                        {hoveredCandle.close >= hoveredCandle.open ? 'BULL' : 'BEAR'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono text-[11px]">
                      <span className="text-slate-400">Open:</span>
                      <span className="text-slate-200 text-right">₹{hoveredCandle.open.toFixed(2)}</span>
                      <span className="text-slate-400">High:</span>
                      <span className="text-emerald-400 text-right">₹{hoveredCandle.high.toFixed(2)}</span>
                      <span className="text-slate-400">Low:</span>
                      <span className="text-rose-400 text-right">₹{hoveredCandle.low.toFixed(2)}</span>
                      <span className="text-slate-400">Close:</span>
                      <span className="text-cyan-300 font-bold text-right">
                        ₹{hoveredCandle.close.toFixed(2)}
                      </span>
                      <span className="text-slate-400">Volume:</span>
                      <span className="text-slate-300 text-right">
                        {hoveredCandle.volume.toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>
                )}

                <svg viewBox="0 0 1000 300" className="w-full h-full overflow-visible">
                  {/* Horizontal Grid lines & Price Labels */}
                  {yTicks.map((price) => {
                    const yPos = 260 - ((price - minPrice) / priceRange) * 230;
                    return (
                      <g key={price}>
                        <line
                          x1="50"
                          y1={yPos}
                          x2="980"
                          y2={yPos}
                          stroke="#ffffff"
                          strokeOpacity={0.06}
                          strokeDasharray="4 4"
                        />
                        <text
                          x="40"
                          y={yPos + 4}
                          fill="#64748b"
                          fontSize="11"
                          fontFamily="monospace"
                          textAnchor="end"
                        >
                          ₹{price}
                        </text>
                      </g>
                    );
                  })}

                  {/* Candlesticks loop */}
                  {data.map((c, idx) => {
                    const n = data.length;
                    const slotWidth = (980 - 70) / n;
                    const centerX = 70 + slotWidth * idx + slotWidth / 2;
                    const candleWidth = Math.max(slotWidth * 0.65, 6);

                    // Y position calculations
                    const yHigh = 260 - ((c.high - minPrice) / priceRange) * 230;
                    const yLow = 260 - ((c.low - minPrice) / priceRange) * 230;
                    const yOpen = 260 - ((c.open - minPrice) / priceRange) * 230;
                    const yClose = 260 - ((c.close - minPrice) / priceRange) * 230;

                    const isGreen = c.close >= c.open;
                    const color = isGreen ? '#10b981' : '#f43f5e';
                    const bodyTop = Math.min(yOpen, yClose);
                    const bodyHeight = Math.max(Math.abs(yClose - yOpen), 3);

                    return (
                      <g
                        key={c.date}
                        className="cursor-pointer transition-opacity hover:opacity-80"
                        onMouseEnter={() => setHoveredCandle(c)}
                        onMouseLeave={() => setHoveredCandle(null)}
                      >
                        {/* Upper and Lower Wick */}
                        <line
                          x1={centerX}
                          y1={yHigh}
                          x2={centerX}
                          y2={yLow}
                          stroke={color}
                          strokeWidth={1.75}
                        />

                        {/* Real Candle Body */}
                        <rect
                          x={centerX - candleWidth / 2}
                          y={bodyTop}
                          width={candleWidth}
                          height={bodyHeight}
                          fill={color}
                          rx={1.5}
                        />

                        {/* Date label at bottom for selected intervals */}
                        {(idx % 3 === 0 || idx === n - 1) && (
                          <text
                            x={centerX}
                            y="285"
                            fill="#64748b"
                            fontSize="10"
                            fontFamily="monospace"
                            textAnchor="middle"
                          >
                            {c.date.slice(5)}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </svg>
              </div>
            ) : (
              /* Line / Area Chart View */
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="priceGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={gradientColor} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={gradientColor} stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff" strokeOpacity={0.05} />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    dy={8}
                  />
                  <YAxis
                    domain={[minPrice, maxPrice]}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    tickFormatter={(val) => `₹${Math.round(val)}`}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length && payload[0]?.payload) {
                        const item = payload[0].payload as ChartCandle;
                        return (
                          <div className="rounded-2xl border border-white/10 bg-[#090d18]/95 p-3.5 shadow-2xl backdrop-blur-2xl text-xs space-y-1.5">
                            <div className="font-bold text-slate-200 border-b border-white/10 pb-1 mb-1">
                              {item.date}
                            </div>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px]">
                              <span className="text-slate-400">Open:</span>
                              <span className="text-slate-200 text-right">₹{item.open.toFixed(2)}</span>
                              <span className="text-slate-400">High:</span>
                              <span className="text-emerald-400 text-right">₹{item.high.toFixed(2)}</span>
                              <span className="text-slate-400">Low:</span>
                              <span className="text-rose-400 text-right">₹{item.low.toFixed(2)}</span>
                              <span className="text-slate-400">Close:</span>
                              <span className="text-cyan-300 font-bold text-right">
                                ₹{item.close.toFixed(2)}
                              </span>
                              <span className="text-slate-400">Volume:</span>
                              <span className="text-slate-300 text-right">
                                {item.volume.toLocaleString('en-IN')}
                              </span>
                            </div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke={strokeColor}
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#priceGlow)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm font-mono border border-dashed border-white/10 rounded-2xl">
              Fetching exchange candles for {ticker}...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
