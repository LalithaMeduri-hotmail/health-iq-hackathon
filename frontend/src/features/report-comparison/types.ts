/**
 * Report Comparison feature types, mirrored from `backend/app/models/report.py`
 * (frontend.instructions.md - derive shared types from the backend contract).
 */

export type LabStatus = 'low' | 'normal' | 'high' | 'critical_flag' | 'unknown';

export type ChangeBucket = 'improved' | 'worsened' | 'unchanged' | 'newlyAbnormal' | 'missing';

export interface ChangedParameter {
  canonicalKey: string;
  displayName: string;
  old: number | null;
  current: number | null;
  unit: string;
  pctChange: number | null;
  status: LabStatus | null;
}

export interface TrendPoint {
  reportDate: string;
  value: number;
}

export interface ComparisonResult {
  runId: string;
  oldReportDate: string;
  currentReportDate: string;
  improved: ChangedParameter[];
  worsened: ChangedParameter[];
  unchanged: ChangedParameter[];
  newlyAbnormal: ChangedParameter[];
  missing: ChangedParameter[];
  trendSeries: Record<string, TrendPoint[]>;
  narrative: string;
}

export interface ReportListItem {
  reportId: string;
  reportDate: string;
  labName: string;
  parameterCount: number;
  abnormalCount: number;
}

export interface ReportListResponse {
  reports: ReportListItem[];
}

export interface LabParameter {
  canonicalKey: string;
  displayName: string;
  value: number;
  unit: string;
  refLow: number | null;
  refHigh: number | null;
  status: LabStatus;
  reportDate: string;
  sourceConfidence: number;
}

export interface SystemCard {
  system: string;
  riskLevel: string;
  summary: string;
}

export interface ReportAnalyzeResponse {
  reportId: string;
  reportDate: string;
  blobPath: string | null;
  parameters: LabParameter[];
  abnormal: LabParameter[];
  systemCards: SystemCard[];
  healthScore: number;
  narrative: string;
}

export interface PdfGenerateResponse {
  pdfBlobUrl: string;
  shareId: string;
  shareUrl: string;
  expiresAt: string;
}
