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
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Research & Risk Preferences</h2>
          <p className="text-xs text-slate-500 mt-1">
            Personalize decision thresholds, investment horizons, and sector exclusion boundaries.
          </p>
        </div>

        {success && (
          <div className="rounded-md bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-700">
            {success}
          </div>
        )}

        <div className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Risk Profile</label>
            <select
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
              className="w-full rounded border border-slate-300 p-2 bg-white text-slate-800"
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Investment Evaluation Horizon
            </label>
            <div className="text-[11px] text-slate-500 mb-1">Model horizon: 6 months</div>
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="w-full rounded border border-slate-300 p-2 bg-white text-slate-800"
            >
              <option value={6}>6 Months (Fixed Model Horizon)</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Sector Exclusions</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newExclusion}
                onChange={(e) => setNewExclusion(e.target.value)}
                placeholder="e.g. Tobacco, Defense, Energy"
                className="flex-1 rounded border border-slate-300 px-3 py-1.5 text-xs"
              />
              <button
                type="button"
                onClick={addExclusion}
                className="rounded bg-slate-200 px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-300"
              >
                Add
              </button>
            </div>

            {exclusions.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {exclusions.map((sector) => (
                  <span
                    key={sector}
                    className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-slate-700 text-[11px]"
                  >
                    {sector}
                    <button
                      type="button"
                      onClick={() => removeExclusion(sector)}
                      className="text-slate-400 hover:text-slate-600"
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
            className="rounded bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>

      {/* Danger Zone: Delete My Data */}
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 shadow-sm space-y-3">
        <h3 className="text-sm font-bold uppercase tracking-wider text-red-900">
          Privacy & Account Deletion
        </h3>
        <p className="text-xs text-red-700 leading-relaxed">
          Permanently removes your account, uploaded research files, vector embeddings, and
          pseudonymises historical quantitative prediction records (severing all personal identity
          links).
        </p>
        <button
          type="button"
          onClick={() => {
            setIsDeleteOpen(true);
            setPasswordInput('');
            setConfirmInput('');
            setDeleteError(null);
          }}
          className="rounded bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700"
        >
          Delete My Data
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {isDeleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h4 className="text-base font-bold text-slate-900">Confirm Irreversible Deletion</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              This action cannot be undone. To permanently delete your data, please enter your current password
              and type <strong className="text-red-600 font-mono">DELETE</strong> in the box below:
            </p>

            {deleteError && (
              <div className="rounded bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
                {deleteError}
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Current Password</label>
              <input
                type="password"
                data-testid="delete-password-input"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="Enter your current password"
                className="w-full rounded border border-slate-300 p-2 text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Confirmation</label>
              <input
                type="text"
                data-testid="delete-confirm-input"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                placeholder="Type DELETE"
                className="w-full rounded border border-slate-300 p-2 text-xs font-mono"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsDeleteOpen(false)}
                className="rounded px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="delete-confirm-button"
                disabled={!passwordInput || confirmInput !== 'DELETE' || deleteDataMutation.isPending}
                onClick={() => deleteDataMutation.mutate()}
                className="rounded bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {deleteDataMutation.isPending ? 'Deleting...' : 'Confirm Deletion'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SettingsPage;
