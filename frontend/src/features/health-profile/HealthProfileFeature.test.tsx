/**
 * Health Profile component tests (frontend.instructions.md - behavior + safety UX, API mocked,
 * never a live backend).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HealthProfileFeature } from './HealthProfileFeature';
import type { ProfileResponse, ReportDetailResponse, SpecialistGuidance } from './types';

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api');
  return {
    ...actual,
    fetchProfile: vi.fn(),
    updatePreferences: vi.fn(),
    suggestSpecialists: vi.fn(),
    analyzeReport: vi.fn(),
    fetchReportDetail: vi.fn(),
  };
});

const api = await import('./api');

const PROFILE: ProfileResponse = {
  profile: {
    userId: 'demo-user',
    demographics: { ageBand: '35-44', sex: 'F', location: 'Bengaluru' },
    consent: { version: '1.0', acceptedAt: '2026-08-27T10:00:00Z', purposes: ['ocr', 'analysis'] },
    preferences: {
      allergies: ['peanut'],
      cuisine: 'south-indian-veg',
      budget: 'low',
      goals: ['reduce-hba1c'],
      location: 'Bengaluru',
    },
    latestSummaryId: 'report-2026-06-14',
    etag: 'etag-1',
  },
  reports: [
    { reportId: 'report-2026-06-14', reportDate: '2026-06-14', healthScore: 68 },
    { reportId: 'report-2026-03-10', reportDate: '2026-03-10', healthScore: 84 },
  ],
  latestSummary: { reportId: 'report-2026-06-14', healthScore: 68 },
};

const GUIDANCE: SpecialistGuidance = {
  categories: [
    {
      specialtyCategory: 'diabetologist',
      parameterGroup: 'metabolic',
      whenToConsult: 'Discuss blood sugar and HbA1c trends.',
      confidence: 0.82,
      source: {
        sourceName: 'MedlinePlus Lab Tests (demo seed)',
        sourceUrl: 'https://medlineplus.gov/lab-tests/',
        sourceDate: '2026-06-01',
      },
    },
  ],
  rationale: 'HbA1c is above the typical range.',
  doctorLinks: [{ name: 'MedlinePlus health topics', url: 'https://medlineplus.gov/', provenance: 'public/demo' }],
  disclaimer: 'Specialist category suggestion only; not a diagnosis or urgency claim.',
};

const DETAIL: ReportDetailResponse = {
  reportId: 'report-2026-06-14',
  reportDate: '2026-06-14',
  labName: 'Demo lab',
  parameters: [
    {
      canonicalKey: 'hba1c',
      displayName: 'HbA1c',
      value: 7.4,
      unit: '%',
      refLow: 4,
      refHigh: 5.6,
      status: 'high',
      reportDate: '2026-06-14',
      sourceConfidence: 0.96,
    },
    {
      canonicalKey: 'creatinine',
      displayName: 'Creatinine',
      value: 0.9,
      unit: 'mg/dL',
      refLow: 0.6,
      refHigh: 1.2,
      status: 'normal',
      reportDate: '2026-06-14',
      sourceConfidence: 0.96,
    },
  ],
  abnormal: [
    {
      canonicalKey: 'hba1c',
      displayName: 'HbA1c',
      value: 7.4,
      unit: '%',
      refLow: 4,
      refHigh: 5.6,
      status: 'high',
      reportDate: '2026-06-14',
      sourceConfidence: 0.96,
    },
  ],
  systemCards: [{ system: 'Blood sugar', riskLevel: 'watch', summary: '1 of 2 outside range.' }],
  healthScore: 92,
  scoreBreakdown: {
    baseScore: 100,
    penalties: [{ canonicalKey: 'hba1c', displayName: 'HbA1c', status: 'high', penalty: 8 }],
    totalPenalty: 8,
    healthScore: 92,
    method: 'Every report starts at 100. This is an educational indicator, not a diagnosis.',
  },
  narrative: 'One value sits outside the typical range.',
};

function envelope<T>(data: T, safetyPass = true) {  return {
    requestId: 'req-1',
    generatedAt: '2026-09-03T00:00:00Z',
    apiVersion: 'v1',
    disclaimer: 'demo disclaimer',
    safety: { pass: safetyPass, notes: [], reviewerVersion: 'safety-1.0.0' },
    data,
  };
}

function renderFeature() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <HealthProfileFeature />
    </QueryClientProvider>,
  );
}

describe('HealthProfileFeature', () => {
  beforeEach(() => {
    vi.mocked(api.fetchProfile).mockResolvedValue(envelope(PROFILE));
    vi.mocked(api.suggestSpecialists).mockResolvedValue(envelope(GUIDANCE));
    vi.mocked(api.updatePreferences).mockResolvedValue(envelope(PROFILE.profile));
    vi.mocked(api.fetchReportDetail).mockResolvedValue(envelope(DETAIL));
  });

  it('renders consent status, report history, and the indicator score', async () => {
    renderFeature();

    expect(await screen.findByText('Accepted v1.0')).toBeInTheDocument();
    expect(screen.getByText('2026-06-14')).toBeInTheDocument();
    expect(screen.getByText('Indicator score 68')).toBeInTheDocument();
    expect(screen.getByText('Latest')).toBeInTheDocument();
  });

  it('keeps report rows collapsed until they are opened', async () => {
    renderFeature();

    const row = await screen.findByRole('button', { name: /2026-06-14/ });
    expect(row).toHaveAttribute('aria-expanded', 'false');
    expect(api.fetchReportDetail).not.toHaveBeenCalled();
  });

  it('expands a report row to explain the score and list out-of-range parameters', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.click(await screen.findByRole('button', { name: /2026-06-14/ }));

    expect(await screen.findByText('Why the score is 92')).toBeInTheDocument();
    expect(screen.getByText('Starting score')).toBeInTheDocument();
    expect(screen.getByText('-8')).toBeInTheDocument();
    expect(screen.getByText('92 / 100')).toBeInTheDocument();
    expect(screen.getByText('Outside the typical range (1 of 2)')).toBeInTheDocument();

    const table = screen.getByRole('table');
    expect(within(table).getByText('HbA1c')).toBeInTheDocument();
    expect(within(table).getByText('7.4 %')).toBeInTheDocument();
    expect(within(table).getByText('4 - 5.6 %')).toBeInTheDocument();
    expect(within(table).getByText('Above range')).toBeInTheDocument();
    // In-range values stay out of the out-of-range table.
    expect(within(table).queryByText('Creatinine')).not.toBeInTheDocument();
  });

  it('collapses an open report row again', async () => {
    const user = userEvent.setup();
    renderFeature();

    const row = await screen.findByRole('button', { name: /2026-06-14/ });
    await user.click(row);
    expect(await screen.findByText('Why the score is 92')).toBeInTheDocument();

    await user.click(row);
    await waitFor(() => expect(screen.queryByText('Why the score is 92')).not.toBeInTheDocument());
  });

  it('shows the specialist category with its provenance and public/demo link flag', async () => {
    renderFeature();

    expect(await screen.findByText('diabetologist')).toBeInTheDocument();
    expect(screen.getByText('82% match')).toBeInTheDocument();
    expect(screen.getByText('public/demo')).toBeInTheDocument();
    expect(
      screen.getByText('Specialist category suggestion only; not a diagnosis or urgency claim.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'MedlinePlus Lab Tests (demo seed)' })).toHaveAttribute(
      'href',
      'https://medlineplus.gov/lab-tests/',
    );
  });

  it('suppresses the suggestion when the safety reviewer did not pass it', async () => {
    vi.mocked(api.suggestSpecialists).mockResolvedValue(envelope(GUIDANCE, false));

    renderFeature();

    expect(
      await screen.findByText('This suggestion was withheld by the safety reviewer and cannot be shown.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('diabetologist')).not.toBeInTheDocument();
  });

  it('pre-fills the preferences form from the stored profile', async () => {
    renderFeature();

    expect(await screen.findByText('peanut')).toBeInTheDocument();
    expect(screen.getByLabelText('Cuisine')).toHaveValue('south-indian-veg');
    expect(screen.getByLabelText('Budget')).toHaveValue('low');
  });

  it('filters the option list as the user searches', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.type(await screen.findByLabelText('Allergies'), 'sh');

    const listbox = screen.getByRole('listbox', { name: 'Allergies' });
    expect(within(listbox).getByRole('option', { name: 'shellfish' })).toBeInTheDocument();
    expect(within(listbox).queryByRole('option', { name: 'egg' })).not.toBeInTheDocument();
  });

  it('adds a searched option to the multi-select and sends it on save', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.type(await screen.findByLabelText('Allergies'), 'shell');
    await user.click(screen.getByRole('option', { name: 'shellfish' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(
        expect.objectContaining({ allergies: ['peanut', 'shellfish'], etag: 'etag-1' }),
      ),
    );
  });

  it('lets the user add a value the curated list does not carry', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.type(await screen.findByLabelText('Allergies'), 'kiwi');
    await user.click(screen.getByRole('option', { name: 'Add "kiwi"' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(
        expect.objectContaining({ allergies: ['peanut', 'kiwi'] }),
      ),
    );
  });

  it('removes a selected chip', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.click(await screen.findByRole('button', { name: 'Remove peanut' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(expect.objectContaining({ allergies: [] })),
    );
  });

  it('replaces the value of a single-select field', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.click(await screen.findByLabelText('Budget'));
    await user.click(screen.getByRole('option', { name: 'high' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(expect.objectContaining({ budget: 'high' })),
    );
  });
});
