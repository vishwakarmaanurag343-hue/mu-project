import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function Register(): React.JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 12) {
      setError('Password must be at least 12 characters');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, password });
      navigate('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#070b12] text-slate-100 p-4 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md relative z-10 space-y-6">
        {/* Market Terminal Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-semibold uppercase tracking-wider shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Terminal Onboarding
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">AlphaLens</h1>
          <p className="text-xs text-slate-400">Institutional-grade quantitative equity research assistant</p>
        </div>

        {/* Auth Glassmorphism Card */}
        <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-[#0e1628]/95 via-[#121c33]/90 to-[#0a0f1d]/95 p-8 shadow-2xl backdrop-blur-2xl space-y-6">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Create Account</h2>
            <p className="text-xs text-slate-400 mt-1">Register for equity factor analysis and calibrated reports</p>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300 backdrop-blur-md flex items-center gap-2"
            >
              <span className="text-rose-400 font-bold">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@firm.com"
                className="w-full rounded-2xl border border-white/10 bg-[#141d33] px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-cyan-500/50 focus:bg-[#18233d] focus:outline-none focus:ring-4 focus:ring-cyan-500/10 transition-all font-mono shadow-inner"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" htmlFor="password">
                Password (min 12 chars)
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-2xl border border-white/10 bg-[#141d33] px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-cyan-500/50 focus:bg-[#18233d] focus:outline-none focus:ring-4 focus:ring-cyan-500/10 transition-all font-mono shadow-inner"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" htmlFor="confirmPassword">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-2xl border border-white/10 bg-[#141d33] px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-cyan-500/50 focus:bg-[#18233d] focus:outline-none focus:ring-4 focus:ring-cyan-500/10 transition-all font-mono shadow-inner"
                required
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-2 rounded-2xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 px-5 py-3.5 text-sm font-bold text-white shadow-lg shadow-cyan-500/20 hover:from-cyan-400 hover:to-indigo-500 transition-all focus:outline-none focus:ring-4 focus:ring-cyan-500/20 disabled:opacity-50 cursor-pointer"
            >
              {submitting ? 'Registering Account...' : 'Register'}
            </button>
          </form>

          <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs text-slate-400">
            <span>Already registered?</span>
            <Link to="/login" className="font-bold text-cyan-400 hover:text-cyan-300 transition-colors">
              Sign In →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
export default Register;
