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
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-xl font-bold text-slate-900">Upload Research Documents</h2>
        <p className="text-xs text-slate-500">
          Upload corporate filings, transcripts, or broker notes (PDF only, max 20 MB, 100 pages).
        </p>

        {/* Privacy Notice */}
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-xs text-blue-900 leading-relaxed">
          <strong>Privacy Notice:</strong> All uploaded documents are parsed in an isolated sandbox.
          By proceeding, you explicitly authorize analysis of this document by the calibrated LLM
          reasoning engine.
        </div>

        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 p-3 text-xs text-red-700">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-md bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-700">
            {success}
          </div>
        )}

        <div className="space-y-4 pt-2">
          <div>
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200 cursor-pointer"
            />
          </div>

          {/* Consent Checkbox */}
          <div className="flex items-start gap-2">
            <input
              id="consent-checkbox"
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <label htmlFor="consent-checkbox" className="text-xs text-slate-700 select-none cursor-pointer">
              My document will be sent to an external LLM provider for analysis
            </label>
          </div>

          <button
            type="button"
            disabled={!file || !consent || uploadMutation.isPending}
            onClick={() => uploadMutation.mutate()}
            className="rounded bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {uploadMutation.isPending ? 'Uploading & Verifying...' : 'Upload Document'}
          </button>
        </div>
      </div>

      {/* Uploads List */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-4">
          Your Uploaded Files
        </h3>
        {isLoading && <p className="text-xs text-slate-500">Loading files...</p>}
        {uploads && uploads.length === 0 && (
          <p className="text-xs text-slate-500">No documents uploaded yet.</p>
        )}
        {uploads && uploads.length > 0 && (
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
            {uploads.map((doc) => (
              <div key={doc.id} className="p-3.5 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-slate-800">{doc.original_filename}</div>
                  <div className="text-slate-500 text-[11px] mt-0.5">
                    {(doc.file_size_bytes / 1024).toFixed(0)} KB · {doc.page_count} pages ·{' '}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(doc.id)}
                  disabled={deleteMutation.isPending}
                  className="text-red-600 hover:text-red-800 font-medium px-2 py-1 rounded hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadPage;

