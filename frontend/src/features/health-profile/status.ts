/** Shared label/tone mapping for lab statuses, risk levels, and indicator scores. */

import type { BadgeTone } from '@/components/ui';

import type { LabParameter, LabStatus } from './types';

export const STATUS_TONES: Record<string, BadgeTone> = {
  high: 'danger',
  low: 'warning',
  critical_flag: 'danger',
  normal: 'success',
  unknown: 'neutral',
};

export const STATUS_LABELS: Record<string, string> = {
  high: 'Above range',
  low: 'Below range',
  critical_flag: 'Flagged',
  normal: 'In range',
  unknown: 'No range on file',
};

export const RISK_TONES: Record<string, BadgeTone> = {
  typical: 'success',
  watch: 'warning',
  discuss: 'danger',
};

export function statusTone(status: LabStatus | string): BadgeTone {
  return STATUS_TONES[status] ?? 'neutral';
}

export function statusLabel(status: LabStatus | string): string {
  return STATUS_LABELS[status] ?? status;
}

export function riskTone(riskLevel: string): BadgeTone {
  return RISK_TONES[riskLevel] ?? 'neutral';
}

/** Backend risk keys rewritten for a reader with no clinical background. */
const RISK_LABELS: Record<string, string> = {
  typical: 'Looks typical',
  watch: 'Worth watching',
  discuss: 'Discuss with a doctor',
};

export function riskLabel(riskLevel: string): string {
  return RISK_LABELS[riskLevel] ?? riskLevel;
}

export function scoreTone(score: number): BadgeTone {
  return score >= 80 ? 'success' : score >= 60 ? 'warning' : 'danger';
}

export function referenceRange(parameter: LabParameter): string {
  if (parameter.refLow === null || parameter.refHigh === null) {
    return 'Not on file';
  }
  return `${parameter.refLow} - ${parameter.refHigh} ${parameter.unit}`;
}

/** Confidence is a ranking signal from the backend, not a probability of any condition. */
export function confidenceLabel(confidence: number): string {
  return `${Math.round(confidence * 100)}% match`;
}

export function formatReportDate(isoDate: string): string {
  const parsed = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return isoDate;
  }
  return parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}
