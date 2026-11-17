import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

export interface EvidenceSource {
  id: string;
  title: string;
  url?: string | null;
}

export interface ClaimItem {
  id: string;
  claim_text: string;
  category: string;
  sentiment: string;
  source_ids: string[];
  sources: EvidenceSource[];
  verified: boolean;
}

export function EvidenceTier({ ticker }: { ticker: string }): React.JSX.Element {
  const [claims, setClaims] = useState<ClaimItem[]>([]);
  const [statusText, setStatusText] = useState<string>('Initializing evidence streaming...');
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setClaims([]);
    setIsStreaming(true);
    setErrorMessage(null);

    const eventSource = new EventSource(`/api/reports/${encodeURIComponent(ticker)}/evidence/stream`);

    eventSource.addEventListener('status', (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setStatusText(payload.message || 'Processing disclosures...');
      } catch {
        // Fallback
      }
    });

    eventSource.addEventListener('claim', (e: MessageEvent) => {
      try {
        const claim = JSON.parse(e.data) as ClaimItem;
        if (claim.verified) {
          setClaims((prev) => [...prev, claim]);
        }
      } catch {
        // Fallback
      }
    });

    eventSource.addEventListener('done', () => {
      setIsStreaming(false);
      setStatusText('All regulatory claims verified.');
      eventSource.close();
    });

    eventSource.addEventListener('error', (e: Event) => {
      const messageEvent = e as MessageEvent;
      if (messageEvent.data) {
        try {
          const errData = JSON.parse(messageEvent.data);
          setErrorMessage(errData.message || 'Evidence stream unavailable.');
        } catch {
          setErrorMessage('Error encountered while streaming evidence.');
        }
      } else {
        setErrorMessage('Connection to evidence stream interrupted.');
      }
      setIsStreaming(false);
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [ticker]);

  return (
    <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-6 lg:p-8 shadow-2xl space-y-5">
      <div className="flex items-center justify-between border-b border-white/5 pb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
            Tier 2: Forward-Only Verified Evidence
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Strictly cites verified disclosures from authorized regulatory domains (BSE, NSE, SEBI).
          </p>
        </div>
        {isStreaming && (
          <span className="flex items-center gap-2 text-xs font-semibold text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-3 py-1 rounded-full animate-pulse">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            Live SSE Stream
          </span>
        )}
      </div>

      {/* Status Progress */}
      {statusText && (
        <div className="rounded-xl bg-[#141d33]/60 border border-white/5 px-4 py-2.5 text-xs text-slate-300 flex items-center gap-2">
          <span className="font-semibold text-cyan-400">Status:</span> {statusText}
        </div>
      )}

      {/* Error alert */}
      {errorMessage && (
        <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-4 text-xs text-amber-300">
          <strong>Notice:</strong> {errorMessage}
        </div>
      )}

      {/* Claims List */}
      <div className="space-y-4">
        {claims.map((claim, index) => {
          const sentimentClass =
            claim.sentiment.toLowerCase() === 'positive'
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : claim.sentiment.toLowerCase() === 'negative'
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                : 'bg-slate-500/10 text-slate-400 border-white/10';

          return (
            <div
              key={claim.id || index}
              data-testid="evidence-card"
              className="rounded-2xl border border-white/5 bg-[#121a2e]/60 p-5 transition-all hover:border-white/10"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  [{index + 1}] {claim.category}
                </span>
                <span
                  className={`text-[10px] font-semibold uppercase px-2.5 py-0.5 rounded-full border ${sentimentClass}`}
                >
                  {claim.sentiment}
                </span>
              </div>

              {/* Secure markdown rendering WITHOUT rehype-raw */}
              <div className="text-sm text-slate-200 leading-relaxed font-sans prose prose-invert max-w-none">
                <ReactMarkdown>{claim.claim_text}</ReactMarkdown>
              </div>

              {/* Numbered Citations */}
              {claim.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/5 flex flex-wrap gap-2 text-xs text-slate-400">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    Verified Citations:
                  </span>
                  {claim.sources.map((src) => (
                    <span key={src.id} className="inline-flex items-center gap-1">
                      {src.url ? (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded-lg bg-white/5 hover:bg-white/10 px-2.5 py-1 text-xs text-cyan-300 border border-white/5 transition-colors"
                        >
                          <span>📄 {src.title}</span>
                        </a>
                      ) : (
                        <span className="text-slate-400">{src.title}</span>
                      )}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

