import React from 'react';
import { useAuth } from './hooks/useAuth';

export default function App(): React.JSX.Element {
  const { user, logout } = useAuth();

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 p-8">
      <div className="max-w-4xl mx-auto space-y-4">
        <header className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-950">AlphaLens</h1>
            <p className="text-slate-600 mt-1">
              Calibrated, evidence-cited equity research assistant (NSE India).
            </p>
          </div>
          {user && (
            <div className="flex items-center space-x-4">
              <span className="text-sm text-slate-600">{user.email}</span>
              <button
                onClick={() => void logout()}
                className="rounded bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300"
              >
                Sign out
              </button>
            </div>
          )}
        </header>
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">System Status</h2>
          <p className="text-sm text-slate-600 mt-2">
            React 18 + Vite frontend active. Authenticated session active. Ready to ingest
            precomputed quantitative factors and stream forward-only LLM evidence.
          </p>
        </section>
      </div>
    </main>
  );
}
