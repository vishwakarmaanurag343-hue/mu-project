import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';

interface UploadItem {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
}

export function UploadPage(): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: uploads, isLoading } = useQuery<UploadItem[]>({
    queryKey: ['uploads'],
    queryFn: () => apiFetch<UploadItem[]>('/api/uploads'),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file || !consent) return;
      const formData = new FormData();
      formData.append('file', file);
      formData.append('consent', 'true');

      return await apiFetch<UploadItem>('/api/uploads', {
        method: 'POST',
        body: formData,
      });
    },
    onSuccess: () => {
      setSuccess('Document uploaded and verified successfully.');
      setFile(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
    onError: (err: Error) => {
      setError(err.message || 'Upload failed');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiFetch(`/api/uploads/${encodeURIComponent(id)}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 p-6 md:p-10">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Preview Release Banner */}
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-xs font-medium text-amber-300 shadow-xl backdrop-blur-md flex items-center gap-3">
          <span className="font-bold uppercase tracking-wider text-[10px] bg-amber-500/20 border border-amber-500/30 text-amber-300 px-2.5 py-1 rounded-full">
            Preview
          </span>
          <span>Document analysis: preview, not enabled in this release</span>
        </div>

        {/* Upload Container */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-8 shadow-2xl space-y-6">
          <div className="border-b border-white/5 pb-4">
            <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
              Upload Research Documents
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Upload corporate filings, transcripts, or broker notes (PDF only, max 20 MB, 100 pages).
            </p>
          </div>

          {/* Privacy Notice Card */}
          <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-5 text-xs text-blue-200 leading-relaxed backdrop-blur-md space-y-1.5">
            <div className="font-bold text-cyan-400 flex items-center gap-1.5">
              <span>🛡️ DPDP Privacy & Sandbox Isolation Notice</span>
            </div>
            <p className="text-slate-300">
              All uploaded documents are parsed in a hardened, memory-bounded subprocess sandbox.
              By proceeding, you explicitly authorize analysis of this document by the calibrated LLM
              reasoning engine. Data already processed by the LLM provider is subject to their retention policy.
            </p>
          </div>

          {error && (
            <div className="rounded-xl bg-rose-500/10 border border-rose-500/20 p-4 text-xs text-rose-300">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-xs text-emerald-300">
              {success}
            </div>
          )}

          <div className="space-y-6 pt-2">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Select PDF File
              </label>
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-400 file:mr-4 file:py-2.5 file:px-5 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-600/20 file:text-cyan-400 hover:file:bg-blue-600/30 file:border-blue-500/30 file:border cursor-pointer bg-[#141d33] rounded-2xl p-2 border border-white/10"
              />
            </div>

            {/* Consent Checkbox */}
            <div className="flex items-start gap-3 rounded-2xl border border-white/5 bg-[#121829]/60 p-4">
              <input
                id="consent-checkbox"
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-white/20 bg-[#141d33] text-cyan-500 focus:ring-cyan-500/30 cursor-pointer"
              />
              <label htmlFor="consent-checkbox" className="text-xs text-slate-300 select-none cursor-pointer leading-relaxed">
                My document will be sent to an external LLM provider for analysis. Data already processed by the LLM provider is subject to their retention policy.
              </label>
            </div>

            <button
              type="button"
              disabled={!file || !consent || uploadMutation.isPending}
              onClick={() => uploadMutation.mutate()}
              className="rounded-2xl bg-gradient-to-r from-blue-600 to-cyan-500 px-6 py-3 text-xs font-bold text-white shadow-glow-blue hover:from-blue-500 hover:to-cyan-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {uploadMutation.isPending ? 'Uploading & Verifying...' : 'Upload Document'}
            </button>
          </div>
        </div>

        {/* Uploads List */}
        <div className="rounded-3xl border border-white/10 bg-[#0d1322]/90 backdrop-blur-xl p-8 shadow-2xl">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400"></span>
            Your Uploaded Research Files
          </h3>
          {isLoading && <p className="text-xs text-slate-400">Loading files...</p>}
          {uploads && uploads.length === 0 && (
            <p className="text-xs text-slate-400">No documents uploaded yet.</p>
          )}
          {uploads && uploads.length > 0 && (
            <div className="divide-y divide-white/5 border border-white/10 rounded-2xl overflow-hidden bg-[#121829]/60">
              {uploads.map((doc) => (
                <div key={doc.id} className="p-4 flex items-center justify-between text-xs hover:bg-white/5 transition-colors">
                  <div>
                    <div className="font-semibold text-white">{doc.original_filename}</div>
                    <div className="text-slate-400 text-[11px] mt-0.5">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB • {doc.page_count} pages •{' '}
                      {new Date(doc.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(doc.id)}
                    disabled={deleteMutation.isPending}
                    className="rounded-xl px-3 py-1.5 text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 text-xs font-medium transition-all"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default UploadPage;
