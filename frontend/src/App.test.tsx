import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';
import { AuthContext } from './hooks/useAuthContext';

describe('App', () => {
  it('renders the AlphaLens header and description', () => {
    const mockAuthValue = {
      user: {
        id: '11111111-1111-1111-1111-111111111111',
        email: 'test@example.com',
        role: 'user',
        is_active: true,
        created_at: '2026-11-13T00:00:00Z',
      },
      isLoading: false,
      isAuthenticated: true,
      login: async () => mockAuthValue.user,
      register: async () => mockAuthValue.user,
      logout: async () => {},
    };

    render(
      <AuthContext.Provider value={mockAuthValue}>
        <App />
      </AuthContext.Provider>,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'AlphaLens' })).toBeInTheDocument();
    expect(
      screen.getByText(/Calibrated, evidence-cited equity research assistant/i),
    ).toBeInTheDocument();
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
  });
});
