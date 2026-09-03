/**
 * Health Profile feature types, mirrored from `backend/app/models/profile.py` and
 * `report.py` (frontend.instructions.md - derive shared types from the backend contract).
 */

import type { SourceRef } from '@/lib/types';

export type LabStatus = 'low' | 'normal' | 'high' | 'critical_flag' | 'unknown';

export interface Demographics {
  ageBand: string | null;
  sex: string | null;
  location: string | null;
}

export interface Consent {
  version: string | null;
  acceptedAt: string | null;
  purposes: string[];
}

export interface Preferences {
  allergies: string[];
  cuisine: string | null;
  budget: string | null;
  goals: string[];
  location: string | null;
}

export interface Profile {
  userId: string;
  demographics: Demographics;
  consent: Consent;
  preferences: Preferences;
  latestSummaryId: string | null;
  etag: string | null;
}

export interface ProfileReportItem {
  reportId: string;
  reportDate: string;
  healthScore: number;
}

export interface LatestSummary {
  reportId: string;
  healthScore: number;
}

export interface ProfileResponse {
  profile: Profile;
  reports: ProfileReportItem[];
  latestSummary: LatestSummary | null;
}

export interface PreferencesUpdate {
  allergies: string[];
  cuisine: string | null;
  budget: string | null;
  goals: string[];
  location: string | null;
  etag: string | null;
}

export interface DoctorLink {
  name: string;
  url: string;
  provenance: string;
}

export interface SpecialistCategory {
  specialtyCategory: string;
  parameterGroup: string;
  whenToConsult: string;
  confidence: number;
  source: SourceRef;
}

export interface SpecialistGuidance {
  categories: SpecialistCategory[];
  rationale: string;
  doctorLinks: DoctorLink[];
  disclaimer: string;
}

export interface SystemCard {
  system: string;
  riskLevel: string;
  summary: string;
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

export interface ScorePenalty {
  canonicalKey: string;
  displayName: string;
  status: LabStatus;
  penalty: number;
}

export interface HealthScoreBreakdown {
  baseScore: number;
  penalties: ScorePenalty[];
  totalPenalty: number;
  healthScore: number;
  method: string;
}

export interface ReportDetailResponse {
  reportId: string;
  reportDate: string;
  labName: string;
  parameters: LabParameter[];
  abnormal: LabParameter[];
  systemCards: SystemCard[];
  healthScore: number;
  scoreBreakdown: HealthScoreBreakdown;
  narrative: string;
}
