import { apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type { GenerateMealPlanRequest, MealPlan, ReportListResponse } from './types';

export function fetchMealPlanReports(): Promise<ApiResponse<ReportListResponse>> {
  return apiClient.get<ReportListResponse>('/api/v1/reports');
}

export function generateMealPlan(request: GenerateMealPlanRequest): Promise<ApiResponse<MealPlan>> {
  return apiClient.post<MealPlan>('/api/v1/meal-plan/generate', request);
}