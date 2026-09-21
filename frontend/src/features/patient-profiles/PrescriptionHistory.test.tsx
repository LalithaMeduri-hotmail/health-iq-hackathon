import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiResponse } from '@/lib/types';

import { PrescriptionHistory } from './PrescriptionHistory';
import type { IssuedPrescription, IssuedPrescriptionListResponse } from './types';

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api');
  return {
    fetchIssuedPrescriptions: vi.fn(),
    issuedPrescriptionPdfUrl: actual.issuedPrescriptionPdfUrl,
  };
});

const api = await import('./api');

function envelope<T>(data: T): ApiResponse<T> {
  return {
    requestId: 'req-1',
    generatedAt: '2026-09-22T00:00:00Z',
    apiVersion: 'v1',
    disclaimer: 'Health information only.',
    safety: { pass: true, notes: [], reviewerVersion: 'safety-1.0.0' },
    data,
  };
}

const PRESCRIPTION: IssuedPrescription = {
  id: 'rx-abc12345',
  accountId: 'acct-1',
  profileId: 'pp-1',
  runId: 'run-1',
  reviewId: 'abc12345',
  status: 'approved',
  issuedAt: '2026-09-21T19:12:21+00:00',
  document: {
    patientName: 'Kavya Menon',
    doctorName: 'Dr. Debopriya Dutta',
    doctorSpecialty: 'General Physician',
    doctorRegistrationNo: 'DEMO-GP-1001',
    reviewedAt: '2026-09-21 19:12 UTC',
    reference: 'abc12345',
    notes: 'Review at the next visit.',
    lines: [
      {
        label: 'Pantocid 40mg',
        maker: 'Sun Pharma',
        generic: 'Pantoprazole (40 mg)',
        form: 'Tablet',
        strength: '40 mg',
        frequency: '1-0-0',
        duration: '14 days',
        decision: 'approved',
        note: 'Switch approved - about 44% less',
        alternative: 'Pantosec 40 mg',
        alternativeMaker: 'Cipla Ltd',
        alternativeGeneric: 'Pantoprazole',
        savingsPct: 44,
        originalMrpInr: 105,
        cheaperMrpInr: 58.4,
      },
    ],
  },
};

function renderHistory(data: IssuedPrescriptionListResponse) {
  vi.mocked(api.fetchIssuedPrescriptions).mockResolvedValue(envelope(data));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <PrescriptionHistory profileId="pp-1" profileName="Kavya Menon" />
    </QueryClientProvider>,
  );
}

describe('PrescriptionHistory', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows what the doctor approved, at the prices recorded then', async () => {
    renderHistory({ profileId: 'pp-1', prescriptions: [PRESCRIPTION] });

    expect(await screen.findByText('Dr. Debopriya Dutta')).toBeInTheDocument();
    expect(screen.getByText('Pantocid 40mg')).toBeInTheDocument();
    expect(screen.getByText('Pantosec 40 mg')).toBeInTheDocument();
    expect(screen.getByText(/about 44% less/)).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  it('links to the stored PDF rather than regenerating it', async () => {
    renderHistory({ profileId: 'pp-1', prescriptions: [PRESCRIPTION] });

    expect(await screen.findByRole('link', { name: /Open prescription/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/api/v1/profiles/pp-1/prescriptions/rx-abc12345/document'),
    );
  });

  it('explains the empty state instead of showing a blank panel', async () => {
    renderHistory({ profileId: 'pp-1', prescriptions: [] });

    expect(await screen.findByText('No Health IQ prescriptions yet')).toBeInTheDocument();
    expect(screen.getByText(/Kavya Menon/)).toBeInTheDocument();
  });
});
