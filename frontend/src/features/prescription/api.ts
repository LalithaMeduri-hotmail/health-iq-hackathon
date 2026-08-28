/**
 * Prescription Analyzer feature API calls (frontend.instructions.md - the ONLY place this
 * feature touches `apiClient`; components/hooks call these functions, never `fetch` directly).
 */

import { ApiError, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type {
  MedicineCorrectionInput,
  MedicineEntity,
  MedicinesAlternativesResponse,
  PrescriptionAnalyzeResponse,
  PrescriptionConfirmResponse,
} from './types';

export interface LowConfidenceConfirmation {
  runId: string;
  items: MedicineEntity[];
}

/** Extracts `{ runId, items[] }` from a `422 low-confidence-ocr` problem response. */
export function parseLowConfidenceError(error: ApiError): LowConfidenceConfirmation | null {
  if (error.problem.type !== 'https://healthiq/errors/low-confidence-ocr') {
    return null;
  }
  const runId = error.problem.errors?.find((e) => e.field === 'runId')?.issue;
  const itemsJson = error.problem.errors?.find((e) => e.field === 'items')?.issue;
  if (!runId || !itemsJson) {
    return null;
  }
  return { runId, items: JSON.parse(itemsJson) as MedicineEntity[] };
}

export async function analyzePrescription(input: {
  consent: boolean;
  file?: File;
  manualMedicines?: string[];
}): Promise<ApiResponse<PrescriptionAnalyzeResponse>> {
  const form = new FormData();
  form.set('consent', String(input.consent));
  if (input.file) {
    form.set('file', input.file);
  }
  if (input.manualMedicines?.length) {
    form.set('manualMedicines', JSON.stringify(input.manualMedicines.map((rawText) => ({ rawText }))));
  }
  return apiClient.post<PrescriptionAnalyzeResponse>('/api/v1/prescriptions/analyze', form);
}

export async function confirmPrescription(
  runId: string,
  corrections: MedicineCorrectionInput[],
): Promise<ApiResponse<PrescriptionConfirmResponse>> {
  return apiClient.post<PrescriptionConfirmResponse>('/api/v1/prescriptions/confirm', { runId, corrections });
}

export async function fetchAlternatives(
  items: MedicineEntity[],
): Promise<ApiResponse<MedicinesAlternativesResponse>> {
  const payload = {
    items: items
      .filter((item) => item.activeIngredient && item.strengthValue && item.strengthUnit && item.dosageForm)
      .map((item) => ({
        brandName: item.brandName,
        activeIngredient: item.activeIngredient,
        strengthValue: item.strengthValue,
        strengthUnit: item.strengthUnit,
        dosageForm: item.dosageForm,
      })),
  };
  return apiClient.post<MedicinesAlternativesResponse>('/api/v1/medicines/alternatives', payload);
}

export { ApiError };
