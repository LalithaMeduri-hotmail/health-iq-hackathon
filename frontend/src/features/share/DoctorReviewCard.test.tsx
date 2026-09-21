import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiResponse } from '@/lib/types';

import { DoctorReviewCard } from './DoctorReviewCard';
import type { MedicineVerdict, ReviewStatusResponse, ReviewSummary } from './api';

vi.mock('@/features/auth', () => ({ useAuth: () => ({ account: null }) }));

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api');
  return {
    reviewDocumentUrl: actual.reviewDocumentUrl,
    fetchDoctors: vi.fn(),
    fetchReviewStatus: vi.fn(),
    requestReview: vi.fn(),
  };
});

const api = await import('./api');

function envelope<T>(data: T): ApiResponse<T> {
  return {
    requestId: 'req-1',
    generatedAt: '2026-09-10T00:00:00Z',
    apiVersion: 'v1',
    disclaimer: 'Health information only.',
    safety: { pass: true, notes: [], reviewerVersion: 'safety-1.0.0' },
    data,
  };
}

function verdict(overrides: Partial<MedicineVerdict> & Pick<MedicineVerdict, 'lineId' | 'label' | 'decision'>): MedicineVerdict {
  return {
    maker: '',
    alternative: '',
    alternativeMaker: '',
    savingsPct: 0,
    originalMrpInr: 0,
    cheaperMrpInr: 0,
    ...overrides,
  };
}

function review(overrides: Partial<ReviewSummary> = {}): ReviewSummary {
  return {
    reviewId: 'abc12345',
    runId: 'run-1',
    doctorName: 'Dr. A. Iyer',
    doctorSpecialty: 'Diabetologist',
    doctorEmailMasked: 'd***@example.invalid',
    status: 'changes_requested',
    requestedAt: '2026-09-10T00:00:00Z',
    decidedAt: '2026-09-10T01:00:00Z',
    notes: 'Halve the Amlong dose.',
    delivery: 'sent',
    decisions: [
      verdict({
        lineId: 'li-1',
        label: 'Glycomet 500mg',
        decision: 'approved',
        alternative: 'Metfor 500 mg',
        alternativeMaker: 'Cipla Ltd',
        savingsPct: 6,
        originalMrpInr: 20.1,
        cheaperMrpInr: 18.9,
      }),
      verdict({ lineId: 'li-2', label: 'Amlong 5mg', decision: 'rejected' }),
    ],
    ...overrides,
  };
}

function renderCard(status: ReviewStatusResponse, detectedPatientName?: string) {
  vi.mocked(api.fetchReviewStatus).mockResolvedValue(envelope(status));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DoctorReviewCard runId="run-1" detectedPatientName={detectedPatientName} />
    </QueryClientProvider>,
  );
}

const DOCTOR = {
  doctorId: 'doc-001',
  name: 'Dr. A. Iyer',
  specialty: 'Diabetologist',
  registrationNo: 'DEMO-DB-1002',
  emailMasked: 'd***@example.invalid',
};

describe('DoctorReviewCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchDoctors).mockResolvedValue(envelope({ doctors: [] }));
  });

  it('asks for the patient name on the field itself instead of blocking the button', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDoctors).mockResolvedValue(envelope({ doctors: [DOCTOR] }));
    renderCard({ runId: 'run-1', reviews: [], approved: false });

    await user.click(await screen.findByRole('checkbox', { name: /Dr. A. Iyer/ }));
    await user.click(screen.getByRole('button', { name: 'Email the review request' }));

    expect(await screen.findByText('Add the patient name before sending.')).toBeInTheDocument();
    expect(api.requestReview).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('Patient name'), 'Ramesh Kumar');
    expect(screen.queryByText('Add the patient name before sending.')).not.toBeInTheDocument();
  });

  it('pre-fills the name read off the prescription and sends it with the request', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDoctors).mockResolvedValue(envelope({ doctors: [DOCTOR] }));
    vi.mocked(api.requestReview).mockResolvedValue(envelope({ reviews: [] }));
    renderCard({ runId: 'run-1', reviews: [], approved: false }, 'Ramesh Kumar');

    await user.click(await screen.findByRole('checkbox', { name: /Dr. A. Iyer/ }));
    await user.click(screen.getByRole('button', { name: 'Email the review request' }));

    await waitFor(() => expect(api.requestReview).toHaveBeenCalledOnce());
    expect(api.requestReview).toHaveBeenCalledWith('run-1', ['doc-001'], 'Ramesh Kumar', {});
  });

  it('shows the doctor verdict for each medicine separately', async () => {
    renderCard({ runId: 'run-1', reviews: [review()], approved: false });

    expect(await screen.findByText('Glycomet 500mg')).toBeInTheDocument();
    expect(screen.getByText('Amlong 5mg')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Not approved')).toBeInTheDocument();
  });

  it('tables each medicine against the alternative it was judged on', async () => {
    renderCard({ runId: 'run-1', reviews: [review()], approved: false });

    expect(await screen.findByRole('columnheader', { name: 'Your medicine' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Health IQ alternative' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: "Doctor's decision" })).toBeInTheDocument();

    expect(screen.getByText('Metfor 500 mg')).toBeInTheDocument();
    expect(screen.getByText(/about 6% less/)).toBeInTheDocument();
    // The refused line had no equivalent, so the cell has to say so rather than sit empty.
    expect(screen.getByText('No equivalent found')).toBeInTheDocument();
  });

  it('offers one summary document covering every verdict', async () => {
    renderCard({ runId: 'run-1', reviews: [review()], approved: false });

    const links = await screen.findAllByRole('link', { name: /Health IQ review summary/ });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute(
      'href',
      expect.stringContaining('/api/v1/reviews/abc12345/documents'),
    );
  });

  it('offers the same single document when nothing was refused', async () => {
    const approved = review({
      status: 'approved',
      decisions: [verdict({ lineId: 'li-1', label: 'Glycomet 500mg', decision: 'approved' })],
    });
    renderCard({ runId: 'run-1', reviews: [approved], approved: true });

    expect(
      await screen.findAllByRole('link', { name: /Health IQ review summary/ }),
    ).toHaveLength(1);
  });

  it('offers no document while the doctor has not answered', async () => {
    const pending = review({ status: 'pending', decidedAt: null, notes: null, decisions: [] });
    renderCard({ runId: 'run-1', reviews: [pending], approved: false });

    expect(await screen.findByText('Waiting for the doctor')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /PDF/ })).not.toBeInTheDocument();
  });
});
