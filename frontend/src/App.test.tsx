import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the AlphaLens header and description', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'AlphaLens' })).toBeInTheDocument();
    expect(
      screen.getByText(/Calibrated, evidence-cited equity research assistant/i),
    ).toBeInTheDocument();
  });
});
