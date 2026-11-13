import React from 'react';

export default function App(): React.JSX.Element {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 p-8">
      <div className="max-w-4xl mx-auto space-y-4">
        <header className="border-b border-slate-200 pb-4">
          <h1 className="text-3xl font-bold tracking-tight text-slate-950">AlphaLens</h1>
          <p className="text-slate-600 mt-1">
            Calibrated, evidence-cited equity research assistant (NSE India).
          </p>
        </header>
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">System Status</h2>
          <p className="text-sm text-slate-600 mt-2">
            React 18 + Vite frontend active. Ready to ingest precomputed quantitative factors and
            stream forward-only LLM evidence.
          </p>
        </section>
      </div>
    </main>
  );
}
