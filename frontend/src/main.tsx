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
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-6">
          <Link to="/" className="font-extrabold text-base tracking-tight text-slate-900">
            AlphaLens
          </Link>
          <div className="flex items-center gap-4 text-slate-600 font-medium">
            <Link to="/" className="hover:text-blue-600">Search</Link>
            <Link to="/upload" className="hover:text-blue-600">Upload</Link>
            <Link to="/history" className="hover:text-blue-600">History</Link>
            <Link to="/calibration" className="hover:text-blue-600">Calibration</Link>
            <Link to="/settings" className="hover:text-blue-600">Settings</Link>
          </div>
        </div>

        {user && (
          <div className="flex items-center gap-3">
            <span className="text-slate-500 font-mono">{user.email}</span>
            <button
              onClick={() => void logout()}
              className="rounded bg-slate-100 hover:bg-slate-200 px-2.5 py-1 text-slate-700 font-semibold"
            >
              Sign out
            </button>
          </div>
        )}
      </nav>

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
