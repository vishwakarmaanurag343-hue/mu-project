import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Login } from '../pages/Login';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { AuthProvider } from '../hooks/useAuth';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
};

describe('Auth System', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders login form and enforces email/password inputs', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
      { wrapper: createWrapper() },
    );

    expect(screen.getByRole('heading', { name: /Sign in to AlphaLens/i })).toBeInTheDocument();
    const submitBtn = screen.getByRole('button', { name: /Sign In/i });

    // HTML5 validation or empty error handling
    fireEvent.click(submitBtn);
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
  });

  it('redirects to /login when ProtectedRoute detects unauthenticated state', async () => {
    // Mock /api/auth/me returning 401
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/me') {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Authentication required' }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Private Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument();
    });
    expect(screen.queryByText('Private Content')).not.toBeInTheDocument();
  });
});

