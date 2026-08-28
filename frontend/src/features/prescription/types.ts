/**
 * Prescription Analyzer feature types, mirrored from `backend/app/models/medicine.py`
 * (frontend.instructions.md - derive shared types from the backend contract).
 */

export interface MedicineEntity {
  lineId: string;
  rawText: string;
  brandName: string | null;
  activeIngredient: string | null;
  strengthValue: number | null;
  strengthUnit: string | null;
  dosageForm: string | null;
  frequency: string | null;
  duration: string | null;
  matchScore: number | null;
  ocrConfidence: number | null;
  needsUserConfirmation: boolean;
}

export interface PrescriptionAnalyzeResponse {
  runId: string;
  blobPath: string | null;
  ocrConfidence: number;
  handwrittenRatio: number;
  items: MedicineEntity[];
  needsConfirmation: MedicineEntity[];
  disclaimers: string[];
}

export interface MedicineCorrectionInput {
  lineId: string;
  brandName?: string;
  strengthValue?: number;
  strengthUnit?: string;
  dosageForm?: string;
}

export interface PrescriptionConfirmResponse {
  items: MedicineEntity[];
}

export interface AlternativeMedicine {
  original: string;
  generic: string;
  cheaper: string;
  originalMrpInr: number;
  cheaperMrpInr: number;
  savingsPct: number;
  savingsEstimated: boolean;
  source: { sourceName: string; sourceUrl: string; sourceDate: string };
  doctorApprovalRequired: boolean;
  matchBasis: string;
}

export interface MedicinesAlternativesResponse {
  alternatives: AlternativeMedicine[];
  unmatched: string[];
}
