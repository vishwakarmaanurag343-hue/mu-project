import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UploadPage } from '../pages/Upload';
import { SettingsPage } from '../pages/Settings';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('User Features UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('enforces required consent checkbox before upload button enables', () => {
    render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>,
      { wrapper: createWrapper() },
    );

    const uploadBtn = screen.getByRole('button', { name: /Upload Document/i });
    expect(uploadBtn).toBeDisabled();

    // Select a file
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const fakeFile = new File(['%PDF-1.4 test content'], 'report.pdf', {
      type: 'application/pdf',
    });
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });

    // Button should still be disabled because consent is unchecked
    expect(uploadBtn).toBeDisabled();

    // Check consent checkbox
    const consentBox = screen.getByLabelText(
      /My document will be sent to an external LLM provider for analysis/i,
    );
    fireEvent.click(consentBox);

    // Now upload button should be enabled
    expect(uploadBtn).toBeEnabled();
  });

  it('enforces typing exact string DELETE in confirmation dialog before deleting data', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
      { wrapper: createWrapper() },
    );

    const openModalBtn = screen.getByRole('button', { name: /Delete My Data/i });
    fireEvent.click(openModalBtn);

    const confirmBtn = screen.getByTestId('delete-confirm-button');
    const input = screen.getByTestId('delete-confirm-input');

    // Initially disabled
    expect(confirmBtn).toBeDisabled();

    // Type partial string
    fireEvent.change(input, { target: { value: 'DEL' } });
    expect(confirmBtn).toBeDisabled();

    // Type exact string
    fireEvent.change(input, { target: { value: 'DELETE' } });
    expect(confirmBtn).toBeEnabled();
  });
});
