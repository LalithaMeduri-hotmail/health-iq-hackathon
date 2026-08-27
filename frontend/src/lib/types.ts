/**
 * Shared API/domain types, mirrored from the backend response envelope
 * (docs/lld/1-low-level-design-overview.md Section 0.3) and `backend/app/models/`.
 *
 * TODO(D4): generate these from the backend OpenAPI schema once routers are implemented
 * (see docs/lld/8-low-level-design-cross-cutting-platform.md Section 7.7 recommendation).
 */

export interface SafetyBlock {
  pass: boolean;
  notes: string[];
  reviewerVersion: string;
}

export interface ApiResponse<TData> {
  requestId: string;
  generatedAt: string;
  apiVersion: string;
  disclaimer: string;
  safety: SafetyBlock;
  data: TData;
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  errors?: Array<{ field: string; issue: string }>;
}

export interface SourceRef {
  sourceName: string;
  sourceUrl: string;
  sourceDate: string;
}
