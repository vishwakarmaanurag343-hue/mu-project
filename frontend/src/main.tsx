import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider } from './hooks/useAuth';
import { SkeletonLoader } from './components/SkeletonLoader';
import './index.css';

// Lazy-load dashboard and report pages to preserve under-200KB bundle budget
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Report = lazy(() => import('./pages/Report'));

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
        <Suspense fallback={<SkeletonLoader />}>
          <Dashboard />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: '/report/:ticker',
    element: (
      <ProtectedRoute>
        <Suspense fallback={<SkeletonLoader />}>
          <Report />
        </Suspense>
      </ProtectedRoute>
    ),
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
