import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiResponse } from '@/lib/types';

import { MealPlannerFeature } from './index';
import type { MealPlan, ReportListResponse } from './types';

vi.mock('./api', () => ({
  fetchMealPlanReports: vi.fn(),
  generateMealPlan: vi.fn(),
}));

const api = await import('./api');

const REPORTS: ReportListResponse = {
  reports: [
    {
      reportId: 'report-demo',
      reportDate: '2026-08-22',
      labName: 'Demo Diagnostics (sample)',
      parameterCount: 8,
      abnormalCount: 3,
    },
  ],
};

const SOURCE = {
  sourceName: 'Nutrition rules',
  sourceUrl: 'https://example.com/nutrition',
  sourceDate: '2026-05-01',
};

const PLAN: MealPlan = {
  conditionTags: ['elevated-glucose'],
  preferences: { cuisine: 'south-indian-veg', budget: 'low', days: 5 },
  days: Array.from({ length: 5 }, (_, index) => ({
    day: index + 1,
    meals: [
      {
        type: 'breakfast',
        items: [`Meal ${index + 1}`],
        notes: 'A grounded meal note.',
        source: SOURCE,
      },
    ],
  })),
  rationale: [{ text: 'Prioritize fiber-rich foods.', source: SOURCE }],
  avoidList: ['peanut (allergen)'],
  disclaimer: 'General nutrition guidance only.',
};

function envelope<T>(data: T, safetyPass = true): ApiResponse<T> {
  return {
    requestId: 'req-1',
    generatedAt: '2026-09-10T00:00:00Z',
    apiVersion: 'v1',
    disclaimer: 'Health information only.',
    safety: {
      pass: safetyPass,
      notes: safetyPass ? [] : ['Safety review suppressed this plan.'],
      reviewerVersion: 'safety-1.0.0',
    },
    data,
  };
}

function renderFeature() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MealPlannerFeature />
    </QueryClientProvider>,
  );
}

describe('MealPlannerFeature', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchMealPlanReports).mockResolvedValue(envelope(REPORTS));
    vi.mocked(api.generateMealPlan).mockResolvedValue(envelope(PLAN));
  });

  it('generates and presents a five-day plan from the selected demo report', async () => {
    const user = userEvent.setup();
    renderFeature();

    expect(await screen.findByRole('option', { name: /Aug 22, 2026/ })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Cuisine'), 'south-indian-veg');
    await user.selectOptions(screen.getByLabelText('Budget'), 'low');
    await user.selectOptions(screen.getByLabelText('Number of days'), '5');
    await user.click(screen.getByRole('button', { name: 'Generate meal plan' }));

    await waitFor(() => expect(api.generateMealPlan).toHaveBeenCalledOnce());
    expect(vi.mocked(api.generateMealPlan).mock.calls[0][0]).toEqual({
        reportId: 'report-demo',
        preferences: { cuisine: 'south-indian-veg', budget: 'low', days: 5 },
    });
    expect(await screen.findByRole('heading', { name: '5-day plan' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: /^Day \d$/ })).toHaveLength(5);
    expect(screen.getByText('peanut (allergen)')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Nutrition rules/ })[0]).toHaveAttribute(
      'href',
      SOURCE.sourceUrl,
    );
  });

  it('does not display meal content when safety review fails', async () => {
    vi.mocked(api.generateMealPlan).mockResolvedValue(envelope(PLAN, false));
    const user = userEvent.setup();
    renderFeature();

    await screen.findByRole('option', { name: /Aug 22, 2026/ });
    await user.click(screen.getByRole('button', { name: 'Generate meal plan' }));

    expect(await screen.findByText('Safety review suppressed this plan.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '5-day plan' })).not.toBeInTheDocument();
  });
});