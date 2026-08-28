/**
 * Prescription Analyzer feature root - upload -> confirm (if needed) -> alternatives flow
 * (FR1.1-FR1.8). Consent is gated globally by `components/ConsentModal` before this renders.
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { ApiError } from '@/lib/apiClient';
import { ErrorState, PageHeader } from '@/components/ui';

import { analyzePrescription, confirmPrescription, parseLowConfidenceError } from './api';
import { ConfirmStep } from './ConfirmStep';
import styles from './prescription.module.css';
import { ResultsStep } from './ResultsStep';
import type { LowConfidenceConfirmation } from './api';
import type { MedicineEntity } from './types';
import { UploadStep } from './UploadStep';

type Step = 'upload' | 'confirm' | 'results';

interface ResultsState {
  runId: string;
  ocrConfidence: number;
  items: MedicineEntity[];
}

function averageConfidence(items: MedicineEntity[]): number {
  const scored = items.map((item) => item.ocrConfidence).filter((value): value is number => value !== null);
  if (scored.length === 0) {
    return 1;
  }
  return scored.reduce((sum, value) => sum + value, 0) / scored.length;
}

export function PrescriptionAnalyzerFeature() {
  const [step, setStep] = useState<Step>('upload');
  const [confirmation, setConfirmation] = useState<LowConfidenceConfirmation | null>(null);
  const [results, setResults] = useState<ResultsState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const analyzeMutation = useMutation({
    mutationFn: analyzePrescription,
    onSuccess: (response) => {
      setErrorMessage(null);
      setResults({
        runId: response.data.runId,
        ocrConfidence: response.data.ocrConfidence,
        items: response.data.items,
      });
      setStep('results');
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        const lowConfidence = parseLowConfidenceError(error);
        if (lowConfidence) {
          setConfirmation(lowConfidence);
          setErrorMessage(null);
          setStep('confirm');
          return;
        }
        setErrorMessage(error.problem.detail);
        return;
      }
      setErrorMessage('Something went wrong while analyzing your prescription.');
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (corrections: { lineId: string; brandName: string }[]) =>
      confirmPrescription(confirmation!.runId, corrections),
    onSuccess: (response) => {
      setResults({
        runId: confirmation!.runId,
        ocrConfidence: averageConfidence(response.data.items),
        items: response.data.items,
      });
      setStep('results');
    },
    onError: () => setErrorMessage('Could not save your corrections. Please try again.'),
  });

  return (
    <section aria-label="Prescription Analyzer">
      <PageHeader
        eyebrow="AI-assisted"
        title="Prescription & Medicine Analyzer"
        description="Upload a prescription or tablet strip and we'll read it, flag anything unclear, and surface doctor-reviewable generic alternatives with estimated savings."
        icon={<span aria-hidden="true">&#8478;</span>}
      />

      <div className={styles.steps}>
        <span className={styles.stepPill} data-active={step === 'upload'}>
          1. Upload
        </span>
        <span className={styles.stepPill} data-active={step === 'confirm'}>
          2. Confirm
        </span>
        <span className={styles.stepPill} data-active={step === 'results'}>
          3. Alternatives
        </span>
      </div>

      {errorMessage && <ErrorState message={errorMessage} onRetry={() => setErrorMessage(null)} retryLabel="Dismiss" />}

      {step === 'upload' && (
        <UploadStep onSubmit={(input) => analyzeMutation.mutate({ consent: true, ...input })} isPending={analyzeMutation.isPending} />
      )}

      {step === 'confirm' && confirmation && (
        <ConfirmStep
          items={confirmation.items}
          onSubmit={(corrections) => confirmMutation.mutate(corrections)}
          isPending={confirmMutation.isPending}
        />
      )}

      {step === 'results' && results && (
        <ResultsStep runId={results.runId} ocrConfidence={results.ocrConfidence} items={results.items} />
      )}
    </section>
  );
}
