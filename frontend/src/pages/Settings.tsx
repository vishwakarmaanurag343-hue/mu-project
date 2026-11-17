import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { useNavigate } from 'react-router-dom';

interface ProfileData {
  risk_level: string;
  investment_horizon_months: number;
  sector_exclusions: string[];
}

export function SettingsPage(): React.JSX.Element {
  const [riskLevel, setRiskLevel] = useState('moderate');
  const [horizon, setHorizon] = useState(6);
  const [exclusions, setExclusions] = useState<string[]>([]);
  const [newExclusion, setNewExclusion] = useState('');
  const [success, setSuccess] = useState<string | null>(null);

  // Delete modal state
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [confirmInput, setConfirmInput] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: profile } = useQuery<ProfileData>({
    queryKey: ['profile'],
    queryFn: () => apiFetch<ProfileData>('/api/profile'),
  });

  useEffect(() => {
    if (profile) {
      setRiskLevel(profile.risk_level);
      setHorizon(profile.investment_horizon_months);
      setExclusions(profile.sector_exclusions || []);
    }
  }, [profile]);

  const updateMutation = useMutation({
    mutationFn: async () => {
      return await apiFetch<ProfileData>('/api/profile', {
        method: 'PUT',
        body: JSON.stringify({
          risk_level: riskLevel,
          investment_horizon_months: horizon,
          sector_exclusions: exclusions,
        }),
      });
    },
    onSuccess: () => {
      setSuccess('Profile updated successfully.');
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });

  const deleteDataMutation = useMutation({
    mutationFn: async () => {
      return await apiFetch('/api/me/data', {
        method: 'DELETE',
        body: JSON.stringify({ password: passwordInput, confirmation: confirmInput }),
      });
    },
    onSuccess: () => {
      queryClient.clear();
      navigate('/login');
    },
    onError: (err: Error) => {
      setDeleteError(err.message || 'Deletion failed');
    },
  });

  const addExclusion = () => {
    if (newExclusion.trim() && !exclusions.includes(newExclusion.trim())) {
      setExclusions([...exclusions, newExclusion.trim()]);
      setNewExclusion('');
    }
  };

  const removeExclusion = (sector: string) => {
    setExclusions(exclusions.filter((s) => s !== sector));
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-8 shadow-2xl space-y-6">
          <div className="border-b border-white/5 pb-4">
            <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
              Research & Risk Preferences
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Personalize decision thresholds, investment horizons, and sector exclusion boundaries.
            </p>
          </div>

          {success && (
            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-xs text-emerald-300">
              {success}
            </div>
          )}

          <div className="space-y-6 text-xs">
            <div>
              <label className="block font-semibold uppercase tracking-wider text-slate-300 mb-2">
                Risk Profile
              </label>
              <select
                value={riskLevel}
                onChange={(e) => setRiskLevel(e.target.value)}
                className="w-full rounded-2xl border border-white/10 p-3.5 bg-[#141d33] text-white focus:outline-none focus:border-cyan-500/50"
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold uppercase tracking-wider text-slate-300 mb-1">
                Investment Evaluation Horizon
              </label>
              <div className="text-[11px] text-slate-400 mb-2">Model horizon: 6 months</div>
              <select
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="w-full rounded-2xl border border-white/10 p-3.5 bg-[#141d33] text-white focus:outline-none focus:border-cyan-500/50"
              >
                <option value={6}>6 Months (Fixed Model Horizon - 126d)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold uppercase tracking-wider text-slate-300 mb-2">
                Sector Exclusions
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newExclusion}
                  onChange={(e) => setNewExclusion(e.target.value)}
                  placeholder="e.g. Tobacco, Defense, Energy..."
                  className="flex-1 rounded-2xl border border-white/10 bg-[#141d33] px-4 py-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                />
                <button
                  type="button"
                  onClick={addExclusion}
                  className="rounded-2xl bg-white/10 hover:bg-white/15 border border-white/10 px-5 py-3 font-bold text-white transition-all"
                >
                  Add
                </button>
              </div>

              {exclusions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {exclusions.map((sector) => (
                    <span
                      key={sector}
                      className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 px-3 py-1 text-cyan-300 text-xs font-medium"
                    >
                      {sector}
                      <button
                        type="button"
                        onClick={() => removeExclusion(sector)}
                        className="text-slate-400 hover:text-rose-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
              className="rounded-2xl bg-gradient-to-r from-blue-600 to-cyan-500 px-6 py-3 font-bold text-white shadow-glow-blue hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all"
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </div>

        {/* Danger Zone: Delete My Data */}
        <div className="rounded-3xl border border-rose-500/20 bg-rose-500/5 p-8 shadow-2xl space-y-4 backdrop-blur-xl">
          <h3 className="text-sm font-bold uppercase tracking-wider text-rose-400 flex items-center gap-2">
            <span>⚠️ DPDP Account Deletion & Right to Erasure</span>
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Permanently removes your account, uploaded research files, vector embeddings, and
            pseudonymises historical quantitative prediction records (severing all personal identity
            links in compliance with India DPDP requirements).
          </p>
          <button
            type="button"
            onClick={() => {
              setIsDeleteOpen(true);
              setPasswordInput('');
              setConfirmInput('');
              setDeleteError(null);
            }}
            className="rounded-2xl bg-rose-600/90 hover:bg-rose-600 px-5 py-2.5 text-xs font-bold text-white shadow-lg transition-all"
          >
            Delete My Data
          </button>
        </div>

        {/* Delete Confirmation Modal */}
        {isDeleteOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
            <div className="w-full max-w-md rounded-3xl border border-white/10 bg-[#0d1322] p-8 shadow-2xl space-y-5">
              <h4 className="text-base font-bold text-white">Confirm Irreversible Deletion</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                This action cannot be undone. To permanently delete your data, please enter your current password
                and type <strong className="text-rose-400 font-mono">DELETE</strong> in the box below:
              </p>

              {deleteError && (
                <div className="rounded-xl bg-rose-500/10 p-3 text-xs text-rose-300 border border-rose-500/20">
                  {deleteError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Current Password</label>
                <input
                  type="password"
                  data-testid="delete-password-input"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="Enter your current password"
                  className="w-full rounded-2xl border border-white/10 bg-[#141d33] p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Confirmation</label>
                <input
                  type="text"
                  data-testid="delete-confirm-input"
                  value={confirmInput}
                  onChange={(e) => setConfirmInput(e.target.value)}
                  placeholder="Type DELETE"
                  className="w-full rounded-2xl border border-white/10 bg-[#141d33] p-3 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setIsDeleteOpen(false)}
                  className="rounded-2xl px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  data-testid="delete-confirm-button"
                  disabled={!passwordInput || confirmInput !== 'DELETE' || deleteDataMutation.isPending}
                  onClick={() => deleteDataMutation.mutate()}
                  className="rounded-2xl bg-rose-600 px-5 py-2 text-xs font-bold text-white hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {deleteDataMutation.isPending ? 'Deleting...' : 'Confirm Deletion'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default SettingsPage;
