/**
 * Doctor-review PDF + secure share feature (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).
 * Shared by the prescription and report-comparison flows, which both hand off a `runId`.
 */

import { apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

export interface PdfGenerateResponse {
  pdfBlobUrl: string;
  shareId: string;
  shareUrl: string;
  expiresAt: string;
}

export type ReviewState = 'pending' | 'approved' | 'changes_requested' | 'rejected' | 'expired';

export interface RegisteredDoctor {
  doctorId: string;
  name: string;
  specialty: string;
  registrationNo: string;
  emailMasked: string;
}

export interface ReviewSummary {
  reviewId: string;
  runId: string;
  doctorName: string;
  doctorSpecialty: string;
  doctorEmailMasked: string;
  status: ReviewState;
  requestedAt: string;
  decidedAt: string | null;
  notes: string | null;
  delivery: string;
}

export interface ReviewStatusResponse {
  runId: string;
  reviews: ReviewSummary[];
  approved: boolean;
}

export async function fetchDoctors(): Promise<ApiResponse<{ doctors: RegisteredDoctor[] }>> {
  return apiClient.get<{ doctors: RegisteredDoctor[] }>('/api/v1/doctors');
}

export async function requestReview(
  runId: string,
  doctorIds: string[],
): Promise<ApiResponse<{ reviews: ReviewSummary[] }>> {
  return apiClient.post<{ reviews: ReviewSummary[] }>('/api/v1/reviews/request', { runId, doctorIds });
}

export async function fetchReviewStatus(runId: string): Promise<ApiResponse<ReviewStatusResponse>> {
  return apiClient.get<ReviewStatusResponse>(`/api/v1/reviews?runId=${encodeURIComponent(runId)}`);
}

export async function generateSharePdf(
  runId: string,
  regenerate = false,
): Promise<ApiResponse<PdfGenerateResponse>> {
  return apiClient.post<PdfGenerateResponse>('/api/v1/pdf/generate', { runId, regenerate });
}

export async function revokeShareLink(shareId: string): Promise<ApiResponse<{ revoked: boolean }>> {
  return apiClient.post<{ revoked: boolean }>(`/api/v1/share/${encodeURIComponent(shareId)}/revoke`);
}
