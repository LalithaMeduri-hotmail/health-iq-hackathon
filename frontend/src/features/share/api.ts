/**
 * Doctor-review PDF + secure share feature (docs/lld/6-low-level-design-doctor-review-pdf-secure-share.md).
 * Shared by the prescription and report-comparison flows, which both hand off a `runId`.
 */

import { absoluteApiUrl, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

export interface PdfGenerateResponse {
  pdfBlobUrl: string;
  shareId: string;
  shareUrl: string;
  expiresAt: string;
}

export type ReviewState = 'pending' | 'approved' | 'changes_requested' | 'rejected' | 'expired';

export type ReviewDecision = 'approved' | 'changes_requested' | 'rejected';

export interface MedicineVerdict {
  lineId: string;
  label: string;
  decision: ReviewDecision;
  maker: string;
  alternative: string;
  alternativeMaker: string;
  savingsPct: number;
  originalMrpInr: number;
  cheaperMrpInr: number;
}

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
  decisions: MedicineVerdict[];
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
  patientName: string,
  selections: Record<string, string> = {},
): Promise<ApiResponse<{ reviews: ReviewSummary[] }>> {
  return apiClient.post<{ reviews: ReviewSummary[] }>('/api/v1/reviews/request', {
    runId,
    doctorIds,
    patientName,
    selections,
  });
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

/** Direct link to a decided review's PDF; served by the API, so it is a navigation, not a fetch. */
export function reviewDocumentUrl(reviewId: string): string {
  return absoluteApiUrl(`/api/v1/reviews/${encodeURIComponent(reviewId)}/documents`);
}
