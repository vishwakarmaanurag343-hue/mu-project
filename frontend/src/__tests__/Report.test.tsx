import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { QuantTier, type QuantData } from '../components/QuantTier';
import { EvidenceTier } from '../components/EvidenceTier';

const mockQuantData: QuantData = {
  ticker: 'RELIANCE.NS',
  probability: 0.68,
  confidence_interval: {
    lower: 0.61,
    upper: 0.74,
  },
  decision_label: 'Overweight',
  as_of: '2026-11-13',
  factor_contributions: [
    { factor: 'Value', contribution: 0.08, score: 1.2 },
    { factor: 'Quality', contribution: 0.12, score: 2.1 },
  ],
  scenarios: {
    bull: { return_pct: 24.5, description: 'Retail EBITDA expansion' },
    bear: { return_pct: -6.8, description: 'Refining margin crack moderation' },
  },
  model_version: 'v1.0.0-quant',
};

describe('Report Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Tier 1 quant data accurately', () => {
    render(<QuantTier data={mockQuantData} />);

    expect(screen.getByRole('heading', { name: 'RELIANCE.NS' })).toBeInTheDocument();
    expect(screen.getByText('Overweight')).toBeInTheDocument();
    expect(screen.getByText('68.0%')).toBeInTheDocument();
    expect(screen.getByText(/61.0% – 74.0%/i)).toBeInTheDocument();
    expect(screen.getByText('Retail EBITDA expansion')).toBeInTheDocument();
  });

  it('renders evidence cards progressively from mock SSE events and sanitizes XSS', async () => {
    const listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
    const closeMock = vi.fn();

    // Mock EventSource
    class MockEventSource {
      close = closeMock;
      addEventListener(type: string, callback: (e: MessageEvent) => void) {
        listeners[type] = listeners[type] || [];
        listeners[type].push(callback);
      }
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).EventSource = MockEventSource;

    const { unmount } = render(<EvidenceTier ticker="RELIANCE.NS" />);

    // Simulate claim SSE event with potential XSS payload
    const mockClaimData = {
      id: 'claim-xss-test',
      claim_text: 'Audited disclosure with `<script>alert(1)</script>` rendered cleanly.',
      category: 'Audit',
      sentiment: 'Positive',
      source_ids: ['src-1'],
      sources: [
        {
          id: 'src-1',
          title: 'BSE Filing',
          url: 'https://www.bseindia.com/filings/doc.pdf',
        },
      ],
      verified: true,
    };

    act(() => {
      listeners['claim']?.forEach((cb) =>
        cb(new MessageEvent('claim', { data: JSON.stringify(mockClaimData) })),
      );
    });

    expect(await screen.findByTestId('evidence-card')).toBeInTheDocument();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(document.querySelector('script[src*="alert"]')).toBeNull();

    // Verify unmount triggers eventSource.close()
    unmount();
    expect(closeMock).toHaveBeenCalled();
  });
});
