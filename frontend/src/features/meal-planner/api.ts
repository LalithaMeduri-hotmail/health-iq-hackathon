import { apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type { GenerateMealPlanRequest, MealPlan, ReportListResponse } from './types';

export function fetchMealPlanReports(profileId?: string | null): Promise<ApiResponse<ReportListResponse>> {
  const query = profileId ? `?profileId=${encodeURIComponent(profileId)}` : '';
  return apiClient.get<ReportListResponse>(`/api/v1/reports${query}`);
}

export function generateMealPlan(request: GenerateMealPlanRequest): Promise<ApiResponse<MealPlan>> {
  return apiClient.post<MealPlan>('/api/v1/meal-plan/generate', request);
}