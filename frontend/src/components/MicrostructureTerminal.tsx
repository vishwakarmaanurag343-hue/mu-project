import React, { useEffect, useState, useRef } from 'react';
import { apiFetch } from '../api/client';

export interface OrderBookLevel {
  price: number;
  size: number;
}

export interface ExecutionFill {
  order_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  order_type: string;
  requested_price: number;
  fill_price: number;
  quantity: number;
  slippage_bps: number;
  latency_microseconds: number;
  timestamp: number;
  status: string;
}

export interface PortfolioState {
  cash_inr: number;
  holdings: Record<string, number>;
  total_trades_executed: number;
  recent_fills: ExecutionFill[];
}

export interface MicrostructureData {
  timestamp: number;
  best_bid: number;
  best_ask: number;
  mid_price: number;
  micro_price: number;
  spread_abs: number;
  spread_bps: number;
  total_bid_depth: number;
  total_ask_depth: number;
  imbalance_ratio: number;
  ofi_score: number;
  pressure_label: string;
  auto_hft_enabled?: boolean;
  portfolio?: PortfolioState;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
}

export function MicrostructureTerminal(): React.JSX.Element {
  const [data, setData] = useState<MicrostructureData | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  const [autoHFT, setAutoHFT] = useState<boolean>(false);
  const [routingOrder, setRoutingOrder] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || '127.0.0.1:8000';
    const wsUrl = `${protocol}//${host}/api/microstructure/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const payload: MicrostructureData = JSON.parse(event.data);
        setData(payload);
        if (payload.auto_hft_enabled !== undefined) {
          setAutoHFT(payload.auto_hft_enabled);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleToggleAutoHFT = async () => {
    const nextState = !autoHFT;
    setAutoHFT(nextState);
    try {
      await apiFetch('/api/microstructure/auto-toggle', {
        method: 'POST',
        body: JSON.stringify({ enabled: nextState }),
      });
    } catch {
      // rollback if request failed
      setAutoHFT(!nextState);
    }
  };

  const handleManualRoute = async (side: 'BUY' | 'SELL') => {
    if (!data) return;
    setRoutingOrder(true);
    try {
      await apiFetch('/api/microstructure/order', {
        method: 'POST',
        body: JSON.stringify({
          symbol: 'BTC/USDT',
          side,
          quantity: 0.05,
          order_type: 'MICRO_PRICE_PEG',
          best_bid: data.best_bid,
          best_ask: data.best_ask,
          micro_price: data.micro_price,
        }),
      });
    } finally {
      setRoutingOrder(false);
    }
  };

  const pressure = data?.pressure_label || '';
  const isStrongBuy = pressure.includes('STRONG BUY');
  const isModerateBuy = pressure.includes('MODERATE BUY') || pressure === 'BUY';
  const isStrongSell = pressure.includes('STRONG SELL');
  const isModerateSell = pressure.includes('MODERATE SELL') || pressure === 'SELL';

  let directionCardClasses = 'bg-[#0e1628]/90 border border-white/10 text-slate-200';
  let badgeIcon = '⚖️';
  let badgeColor = 'bg-white/10 text-slate-300 border-white/20';

  if (isStrongBuy) {
    directionCardClasses =
      'bg-gradient-to-br from-emerald-950/80 via-emerald-900/40 to-[#0e1628] border-2 border-emerald-400/80 shadow-2xl shadow-emerald-500/25 ring-2 ring-emerald-400/30';
    badgeIcon = '🚀';
    badgeColor = 'bg-emerald-500/25 text-emerald-300 border-emerald-400/60 animate-pulse';
  } else if (isModerateBuy) {
    directionCardClasses =
      'bg-emerald-950/40 border border-emerald-500/40 shadow-xl shadow-emerald-500/10';
    badgeIcon = '▲';
    badgeColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  } else if (isStrongSell) {
    directionCardClasses =
      'bg-gradient-to-br from-rose-950/80 via-rose-900/40 to-[#0e1628] border-2 border-rose-400/80 shadow-2xl shadow-rose-500/25 ring-2 ring-rose-400/30';
    badgeIcon = '⚠️';
    badgeColor = 'bg-rose-500/25 text-rose-300 border-rose-400/60 animate-pulse';
  } else if (isModerateSell) {
    directionCardClasses =
      'bg-rose-950/40 border border-rose-500/40 shadow-xl shadow-rose-500/10';
    badgeIcon = '▼';
    badgeColor = 'bg-rose-500/20 text-rose-400 border-rose-500/40';
  }

  const maxBidSize = data?.bids.length ? Math.max(...data.bids.map((b) => b.size)) : 1;
  const maxAskSize = data?.asks.length ? Math.max(...data.asks.map((a) => a.size)) : 1;
  const overallMaxSize = Math.max(maxBidSize, maxAskSize, 0.001);

  const portfolio = data?.portfolio;

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#0a0f1d] via-[#0f172a] to-[#070b14] p-6 lg:p-8 shadow-2xl backdrop-blur-2xl space-y-6">
      {/* Background ambient radial lighting */}
      <div className="absolute top-0 right-1/4 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* Header bar: Title + Automated HFT Gateway Controller Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                connected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'
              }`}
            ></span>
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-300">
              Automated HFT Execution Gateway & Microstructure Router
            </span>
            <span className="text-[10px] bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 px-2 py-0.5 rounded-full font-mono font-bold">
              Sub-Millisecond Engine
            </span>
          </div>
          <h3 className="text-xl lg:text-2xl font-black text-white mt-1">
            Real-Time Order Flow Imbalance & Auto-Routing Peg
          </h3>
        </div>

        {/* HFT Mode Controls & Status */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleToggleAutoHFT}
            className={`px-4 py-2 rounded-2xl text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 shadow-lg ${
              autoHFT
                ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-900 shadow-emerald-500/25 border-2 border-emerald-400 animate-pulse'
                : 'bg-[#152039] text-slate-300 hover:text-white border border-white/10 hover:border-cyan-500/40'
            }`}
          >
            <span>{autoHFT ? '⚡ Auto-HFT Active' : '⏸ Auto-HFT Paused'}</span>
          </button>
        </div>
      </div>

      {/* Main Microstructure Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="bg-[#0e1628]/90 border border-white/10 rounded-2xl p-4 shadow-xl">
          <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
            Micro-Price (Weighted Mid)
          </div>
          <div className="text-xl font-black text-cyan-400 mt-1 font-mono">
            ${data?.micro_price ? data.micro_price.toFixed(2) : '—'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
            Mid: ${data?.mid_price ? data.mid_price.toFixed(2) : '—'}
          </div>
        </div>

        <div className="bg-[#0e1628]/90 border border-white/10 rounded-2xl p-4 shadow-xl">
          <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
            Bid-Ask Spread
          </div>
          <div className="text-xl font-black text-slate-200 mt-1 font-mono">
            ${data?.spread_abs ? data.spread_abs.toFixed(2) : '—'}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5 font-mono">
            {data?.spread_bps ? `${data.spread_bps.toFixed(2)} bps` : '—'}
          </div>
        </div>

        <div className="bg-[#0e1628]/90 border border-white/10 rounded-2xl p-4 shadow-xl">
          <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
            Order Flow Imbalance (OFI)
          </div>
          <div
            className={`text-xl font-black mt-1 font-mono ${
              data?.ofi_score && data.ofi_score >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {data?.ofi_score !== undefined
              ? data.ofi_score > 0
                ? `+${data.ofi_score.toFixed(3)}`
                : data.ofi_score.toFixed(3)
              : '—'}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Rolling Sub-Second Flow</div>
        </div>

        {/* Highlighted Sub-Second Direction Card */}
        <div className={`rounded-2xl p-4 transition-all duration-300 relative overflow-hidden ${directionCardClasses}`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-black text-slate-300">
              Sub-Second Direction
            </span>
            <span className={`text-[10px] font-black px-2 py-0.5 rounded-full border flex items-center gap-1 ${badgeColor}`}>
              <span>{badgeIcon}</span>
              <span>{isStrongBuy || isModerateBuy ? 'BUY' : isStrongSell || isModerateSell ? 'SELL' : 'NEUTRAL'}</span>
            </span>
          </div>

          <div
            className={`text-base lg:text-lg font-black mt-2 uppercase tracking-tight flex items-center gap-1.5 ${
              isStrongBuy || isModerateBuy
                ? 'text-emerald-400 drop-shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                : isStrongSell || isModerateSell
                  ? 'text-rose-400 drop-shadow-[0_0_12px_rgba(244,63,94,0.5)]'
                  : 'text-slate-300'
            }`}
          >
            <span>{data?.pressure_label || 'COMPUTING...'}</span>
          </div>

          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-white/10 text-[10px] font-mono">
            <span className="text-slate-400">Book Imbalance:</span>
            <span
              className={`font-black ${
                isStrongBuy || isModerateBuy
                  ? 'text-emerald-300'
                  : isStrongSell || isModerateSell
                    ? 'text-rose-300'
                    : 'text-slate-200'
              }`}
            >
              {data?.imbalance_ratio !== undefined ? `${(data.imbalance_ratio * 100).toFixed(1)}%` : '0%'}
            </span>
          </div>
        </div>
      </div>

      {/* Manual High-Frequency Execution Buttons (Micro-Price Peg) */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-2xl border border-white/10 bg-[#0c1424]/90">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-300 font-mono">
            Direct Market Access (DMA) Peg:
          </span>
          <span className="text-xs font-black text-cyan-400 font-mono">
            P_micro = ${data?.micro_price.toFixed(2) ?? '—'}
          </span>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            onClick={() => handleManualRoute('BUY')}
            disabled={routingOrder || !data}
            className="flex-1 sm:flex-none px-5 py-2.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/40 text-xs font-black uppercase tracking-wider transition-all shadow-md disabled:opacity-50"
          >
            🚀 BUY Peg Order (0.05 BTC)
          </button>
          <button
            onClick={() => handleManualRoute('SELL')}
            disabled={routingOrder || !data}
            className="flex-1 sm:flex-none px-5 py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 border border-rose-500/40 text-xs font-black uppercase tracking-wider transition-all shadow-md disabled:opacity-50"
          >
            ⚠️ SELL Peg Order (0.05 BTC)
          </button>
        </div>
      </div>

      {/* Level 2 Depth Ladder (Bids vs Asks) */}
      <div className="rounded-2xl border border-white/10 bg-[#0c1222]/90 p-5 space-y-3">
        <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-white/10 pb-2">
          <span>Level 2 Bid Depth Ladder</span>
          <span>Level 2 Ask Depth Ladder</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Bids Column */}
          <div className="space-y-1.5">
            {data?.bids.map((b, idx) => {
              const widthPct = Math.min((b.size / overallMaxSize) * 100, 100);
              return (
                <div
                  key={`bid-${idx}`}
                  className="relative flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#0f172a] overflow-hidden text-xs font-mono"
                >
                  <div
                    className="absolute left-0 top-0 bottom-0 bg-emerald-500/20 border-r border-emerald-500/40"
                    style={{ width: `${widthPct}%` }}
                  ></div>
                  <span className="relative z-10 text-emerald-400 font-bold">
                    ${b.price.toFixed(2)}
                  </span>
                  <span className="relative z-10 text-slate-300">{b.size.toFixed(4)}</span>
                </div>
              );
            })}
          </div>

          {/* Asks Column */}
          <div className="space-y-1.5">
            {data?.asks.map((a, idx) => {
              const widthPct = Math.min((a.size / overallMaxSize) * 100, 100);
              return (
                <div
                  key={`ask-${idx}`}
                  className="relative flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#0f172a] overflow-hidden text-xs font-mono"
                >
                  <div
                    className="absolute right-0 top-0 bottom-0 bg-rose-500/20 border-l border-rose-500/40"
                    style={{ width: `${widthPct}%` }}
                  ></div>
                  <span className="relative z-10 text-slate-300">{a.size.toFixed(4)}</span>
                  <span className="relative z-10 text-rose-400 font-bold">
                    ${a.price.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Execution Fills Audit Log (Sub-Millisecond Fill Benchmark) */}
      {portfolio && portfolio.recent_fills.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-[#080d1a]/95 p-5 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-white/10 pb-2">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              Live HFT Execution Fills Audit & Microsecond Latency Log
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              Total Executed: {portfolio.total_trades_executed} Trades
            </span>
          </div>

          <div className="divide-y divide-white/5 overflow-x-auto max-h-48 scrollbar-none">
            {portfolio.recent_fills.map((fill) => (
              <div
                key={fill.order_id}
                className="py-2 flex items-center justify-between text-xs font-mono gap-4 min-w-[550px]"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`font-black px-2 py-0.5 rounded text-[10px] ${
                      fill.side === 'BUY'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    {fill.side}
                  </span>
                  <span className="text-slate-300 font-bold">{fill.order_id}</span>
                  <span className="text-slate-400 text-[11px]">{fill.order_type}</span>
                </div>

                <div className="flex items-center gap-5 text-[11px]">
                  <div>
                    <span className="text-slate-500 mr-1">Fill:</span>
                    <span className="text-white font-bold">${fill.fill_price.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Qty:</span>
                    <span className="text-cyan-300">{fill.quantity}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Slippage:</span>
                    <span className="text-amber-400">{fill.slippage_bps} bps</span>
                  </div>
                  <div className="bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded text-cyan-300 font-bold">
                    ⏱ {fill.latency_microseconds} μs
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
export default MicrostructureTerminal;
