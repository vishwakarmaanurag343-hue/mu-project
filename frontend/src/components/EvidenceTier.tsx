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
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-base font-bold text-slate-900">
            Tier 2: Forward-Only Verified Evidence
          </h3>
          <p className="text-xs text-slate-500">
            Strictly cites verified disclosures from authorized regulatory domains (BSE, NSE, SEBI).
          </p>
        </div>
        {isStreaming && (
          <span className="flex items-center gap-2 text-xs font-medium text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full animate-pulse">
            <span className="h-2 w-2 rounded-full bg-blue-600" />
            Live SSE Stream
          </span>
        )}
      </div>

      {/* Status Progress */}
      {statusText && (
        <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-700">Status:</span> {statusText}
        </div>
      )}

      {/* Error alert */}
      {errorMessage && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
          <strong>Notice:</strong> {errorMessage}
        </div>
      )}

      {/* Claims List */}
      <div className="space-y-4">
        {claims.map((claim, index) => {
          const sentimentClass =
            claim.sentiment.toLowerCase() === 'positive'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : claim.sentiment.toLowerCase() === 'negative'
                ? 'bg-rose-50 text-rose-700 border-rose-200'
                : 'bg-slate-50 text-slate-700 border-slate-200';

          return (
            <div
              key={claim.id || index}
              data-testid="evidence-card"
              className="rounded-lg border border-slate-200 p-4 transition-all hover:border-slate-300"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  [{index + 1}] {claim.category}
                </span>
                <span
                  className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${sentimentClass}`}
                >
                  {claim.sentiment}
                </span>
              </div>

              {/* Secure markdown rendering WITHOUT rehype-raw */}
              <div className="text-sm text-slate-800 leading-relaxed">
                <ReactMarkdown>{claim.claim_text}</ReactMarkdown>
              </div>

              {/* Numbered Citations */}
              {claim.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-slate-100 flex flex-wrap gap-2 text-xs text-slate-500">
                  <span className="font-medium">Sources:</span>
                  {claim.sources.map((src) => (
                    <span key={src.id} className="inline-flex items-center gap-1">
                      {src.url ? (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 underline hover:text-blue-800"
                        >
                          {src.title}
                        </a>
                      ) : (
                        <span className="text-slate-600">{src.title}</span>
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

