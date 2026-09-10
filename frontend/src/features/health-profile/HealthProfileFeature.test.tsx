/**
 * Health Profile component tests (frontend.instructions.md - behavior + safety UX, API mocked,
 * never a live backend).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
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
      ],
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
  systemCards: [
    {
      system: 'Blood sugar',
      riskLevel: 'watch',
      summary: '1 of 2 values sit outside the typical range: HbA1c (high).',
      parameters: ['hba1c', 'creatinine'],
    },
  ],
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
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <HealthProfileFeature />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function openTab(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole('tab', { name: new RegExp(name) }));
}

describe('HealthProfileFeature', () => {
  beforeEach(() => {
    vi.mocked(api.fetchProfile).mockResolvedValue(envelope(PROFILE));
    vi.mocked(api.suggestSpecialists).mockResolvedValue(envelope(GUIDANCE));
    vi.mocked(api.updatePreferences).mockResolvedValue(envelope(PROFILE.profile));
    vi.mocked(api.fetchReportDetail).mockResolvedValue(envelope(DETAIL));
  });

  it('summarises the latest score, consent, and score movement', async () => {
    renderFeature();

    expect(await screen.findByText('Consent v1.0 accepted')).toBeInTheDocument();
    expect(screen.getByText('Reports on record')).toBeInTheDocument();
    expect(screen.getByText('-16 points')).toBeInTheDocument();
  });

  it('summarises each body system on the overview tab', async () => {
    renderFeature();

    expect(await screen.findByText('Blood sugar')).toBeInTheDocument();
    expect(screen.getByText('What stood out (1 of 2 values)')).toBeInTheDocument();
    expect(screen.getByText('Worth watching')).toBeInTheDocument();
    expect(screen.getByText(/1 outside range/)).toBeInTheDocument();
    expect(screen.getByText('Tap to see who to consult')).toBeInTheDocument();
    // The full results table belongs to the report history, not the overview.
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('opens a body system to name the specialist and split in-range from out-of-range values', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.click(await screen.findByRole('button', { name: /Blood sugar/ }));

    expect(screen.getByText('Who to consult')).toBeInTheDocument();
    expect(screen.getByText('diabetologist')).toBeInTheDocument();
    expect(screen.getByText('82% match')).toBeInTheDocument();
    expect(screen.getByText('Discuss blood sugar and HbA1c trends.')).toBeInTheDocument();
    expect(screen.getByText('Outside the typical range (1)')).toBeInTheDocument();
    expect(screen.getByText('Within the typical range (1)')).toBeInTheDocument();
    // Also rendered in "What stood out", so the value card appears twice on this tab.
    expect(screen.getAllByText('1.8 % above the typical maximum of 5.6 %')).toHaveLength(2);
    expect(screen.getByText('Creatinine')).toBeInTheDocument();
  });

  it('keeps the disclaimer and a provenance link on the suggestion', async () => {
    const user = userEvent.setup();
    renderFeature();

    await user.click(await screen.findByRole('button', { name: /Blood sugar/ }));

    expect(
      screen.getByText(/Specialist category suggestion only; not a diagnosis or urgency claim\./),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Source' })).toHaveAttribute(
      'href',
      'https://medlineplus.gov/lab-tests/',
    );
    expect(screen.getByRole('link', { name: 'Find a doctor' })).toHaveAttribute('href', 'https://medlineplus.gov/');
  });

  it('suppresses the suggestion when the safety reviewer did not pass it', async () => {
    vi.mocked(api.suggestSpecialists).mockResolvedValue(envelope(GUIDANCE, false));

    const user = userEvent.setup();
    renderFeature();

    expect(
      await screen.findByText('Specialty suggestions were withheld by the safety reviewer and cannot be shown.'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Blood sugar/ }));
    expect(screen.queryByText('diabetologist')).not.toBeInTheDocument();
  });

  it('lists analyzed reports on the report history tab', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Report history');

    expect(screen.getByRole('button', { name: /Jun 14, 2026/ })).toBeInTheDocument();
    expect(screen.getByText('Indicator score 68')).toBeInTheDocument();
    expect(screen.getByText('Latest')).toBeInTheDocument();
  });

  it('keeps report rows collapsed until they are opened', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Report history');

    const row = screen.getByRole('button', { name: /Jun 14, 2026/ });
    expect(row).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('expands a report row to list every result in a table', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Report history');

    await user.click(screen.getByRole('button', { name: /Jun 14, 2026/ }));

    expect(await screen.findByText('All 2 results (1 outside the typical range)')).toBeInTheDocument();

    const table = screen.getByRole('table');
    expect(within(table).getByText('HbA1c')).toBeInTheDocument();
    expect(within(table).getByText('7.4 %')).toBeInTheDocument();
    expect(within(table).getByText('4 - 5.6 %')).toBeInTheDocument();
    expect(within(table).getByText('Above range')).toBeInTheDocument();
    expect(within(table).getByText('Creatinine')).toBeInTheDocument();
  });

  it('collapses an open report row again', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Report history');

    const row = screen.getByRole('button', { name: /Jun 14, 2026/ });
    await user.click(row);
    expect(await screen.findByText('All 2 results (1 outside the typical range)')).toBeInTheDocument();

    await user.click(row);
    await waitFor(() =>
      expect(screen.queryByText('All 2 results (1 outside the typical range)')).not.toBeInTheDocument(),
    );
  });

  it('pre-fills the preferences form from the stored profile', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Preferences');

    expect(await screen.findByText('peanut')).toBeInTheDocument();
    expect(screen.getByLabelText('Cuisine')).toHaveValue('south-indian-veg');
    expect(screen.getByLabelText('Budget')).toHaveValue('low');
  });

  it('filters the option list as the user searches', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Preferences');

    await user.type(await screen.findByLabelText('Allergies'), 'sh');

    const listbox = screen.getByRole('listbox', { name: 'Allergies' });
    expect(within(listbox).getByRole('option', { name: 'shellfish' })).toBeInTheDocument();
    expect(within(listbox).queryByRole('option', { name: 'egg' })).not.toBeInTheDocument();
  });

  it('adds a searched option to the multi-select and sends it on save', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Preferences');

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
    await openTab(user, 'Preferences');

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
    await openTab(user, 'Preferences');

    await user.click(await screen.findByRole('button', { name: 'Remove peanut' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(expect.objectContaining({ allergies: [] })),
    );
  });

  it('replaces the value of a single-select field', async () => {
    const user = userEvent.setup();
    renderFeature();
    await openTab(user, 'Preferences');

    await user.click(await screen.findByLabelText('Budget'));
    await user.click(screen.getByRole('option', { name: 'high' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));

    await waitFor(() =>
      expect(api.updatePreferences).toHaveBeenCalledWith(expect.objectContaining({ budget: 'high' })),
    );
  });
});
