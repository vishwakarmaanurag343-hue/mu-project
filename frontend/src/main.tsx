import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider, Link, Outlet } from 'react-router-dom';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { SkeletonLoader } from './components/SkeletonLoader';
import './index.css';

// Lazy-load pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Report = lazy(() => import('./pages/Report'));
const UploadPage = lazy(() => import('./pages/Upload'));
const HistoryPage = lazy(() => import('./pages/History'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const CalibrationPage = lazy(() => import('./pages/Calibration'));

function NavigationLayout(): React.JSX.Element {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Glass Navigation Bar */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#0d1322]/80 border-b border-white/5 px-6 py-3.5 flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 p-[1px] shadow-glow-blue">
              <div className="w-full h-full bg-[#0d1322] rounded-[11px] flex items-center justify-center">
                <span className="text-cyan-400 font-black text-sm">α</span>
              </div>
            </div>
            <span className="font-extrabold text-base tracking-tight text-white group-hover:text-cyan-400 transition-colors">
              AlphaLens
            </span>
          </Link>

          <nav className="flex items-center gap-1 bg-[#131b2e]/60 p-1 rounded-xl border border-white/5 text-xs">
            <Link
              to="/"
              className="px-3.5 py-1.5 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
            >
              Dashboard
            </Link>
            <Link
              to="/upload"
              className="px-3.5 py-1.5 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
            >
              Upload
            </Link>
            <Link
              to="/history"
              className="px-3.5 py-1.5 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
            >
              Audit History
            </Link>
            <Link
              to="/calibration"
              className="px-3.5 py-1.5 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
            >
              Reliability Lab
            </Link>
            <Link
              to="/settings"
              className="px-3.5 py-1.5 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
            >
              Settings
            </Link>
          </nav>
        </div>

        {user && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5 bg-[#131b2e]/80 border border-white/10 px-3 py-1.5 rounded-xl">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
              <span className="text-xs text-slate-300 font-mono">{user.email}</span>
            </div>
            <button
              onClick={() => void logout()}
              className="rounded-xl bg-white/5 hover:bg-rose-500/10 hover:text-rose-400 border border-white/10 hover:border-rose-500/30 px-3 py-1.5 text-xs text-slate-300 font-semibold transition-all"
            >
              Sign out
            </button>
          </div>
        )}
      </header>

      <div className="flex-1">
        <Suspense fallback={<div className="p-8 max-w-4xl mx-auto"><SkeletonLoader /></div>}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: false,
    },
  },
});

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <NavigationLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: '', element: <Dashboard /> },
      { path: 'report/:ticker', element: <Report /> },
      { path: 'upload', element: <UploadPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'calibration', element: <CalibrationPage /> },
    ],
  },
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/register',
    element: <Register />,
  },
]);

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Failed to find root element');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
