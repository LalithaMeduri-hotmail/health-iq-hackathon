/**
 * Report Comparison feature API calls (frontend.instructions.md - the ONLY place this feature
 * touches `apiClient`; components/hooks call these functions, never `fetch` directly).
 */

import { ApiError, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type {
  ComparisonResult,
  PdfGenerateResponse,
  ReportAnalyzeResponse,
  ReportListResponse,
} from './types';

export async function fetchReports(): Promise<ApiResponse<ReportListResponse>> {
  return apiClient.get<ReportListResponse>('/api/v1/reports');
}

export async function analyzeReport(file: File): Promise<ApiResponse<ReportAnalyzeResponse>> {
  const form = new FormData();
  form.set('consent', 'true');
  form.set('file', file);
  return apiClient.post<ReportAnalyzeResponse>('/api/v1/reports/analyze', form);
}

export async function compareReports(
  oldReportId: string,
  currentReportId: string,
): Promise<ApiResponse<ComparisonResult>> {
  return apiClient.post<ComparisonResult>('/api/v1/reports/compare', { oldReportId, currentReportId });
}

export async function generateSharePdf(runId: string): Promise<ApiResponse<PdfGenerateResponse>> {
  return apiClient.post<PdfGenerateResponse>('/api/v1/pdf/generate', { runId });
}

export { ApiError };
