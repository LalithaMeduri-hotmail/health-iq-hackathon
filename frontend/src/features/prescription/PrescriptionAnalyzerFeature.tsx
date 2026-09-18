/**
 * Prescription Analyzer feature root - upload -> confirm -> alternatives flow (FR1.1-FR1.8).
 * Confirmation is unconditional: a clean digital PDF still gets checked by the user, because a
 * high read confidence says the text was legible, not that it was the right medicine.
 * Consent is gated globally by `components/ConsentModal` before this renders.
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { ApiError } from '@/lib/apiClient';
import { ErrorState, PageHeader } from '@/components/ui';

import { analyzePrescription, confirmPrescription, parseLowConfidenceError } from './api';
import { ConfirmStep } from './ConfirmStep';
import { PatientIdentityDialog } from './PatientIdentityDialog';
import styles from './prescription.module.css';
import { ResultsStep } from './ResultsStep';
import type { MedicineCorrectionInput, MedicineEntity } from './types';
import { UploadStep } from './UploadStep';

type Step = 'upload' | 'confirm' | 'results';

interface ResultsState {
  runId: string;
  ocrConfidence: number;
  items: MedicineEntity[];
}

/** What the user verifies, plus the read confidence to carry into the results header. */
interface ConfirmState {
  runId: string;
  items: MedicineEntity[];
  ocrConfidence: number;
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
  const [confirmation, setConfirmation] = useState<ConfirmState | null>(null);
  const [results, setResults] = useState<ResultsState | null>(null);
  // Read off the uploaded prescription; it pre-fills the name on the doctor-signed document.
  const [patientName, setPatientName] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPatientDialogOpen, setIsPatientDialogOpen] = useState(false);

  const analyzeMutation = useMutation({
    mutationFn: analyzePrescription,
    onSuccess: (response) => {
      setErrorMessage(null);
      setPatientName(response.data.patientName);
      setConfirmation({
        runId: response.data.runId,
        items: response.data.items,
        ocrConfidence: response.data.ocrConfidence,
      });
      setIsPatientDialogOpen(true);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError) {
        const lowConfidence = parseLowConfidenceError(error);
        if (lowConfidence) {
          setPatientName(lowConfidence.patientName);
          setConfirmation({
            runId: lowConfidence.runId,
            items: lowConfidence.items,
            ocrConfidence: averageConfidence(lowConfidence.items),
          });
          setErrorMessage(null);
          setIsPatientDialogOpen(true);
          return;
        }
        setErrorMessage(error.problem.detail);
        return;
      }
      setErrorMessage('Something went wrong while analyzing your prescription.');
    },
  });

  const confirmMutation = useMutation({
    mutationFn: ({ runId, corrections }: { runId: string; corrections: MedicineCorrectionInput[] }) =>
      confirmPrescription(runId, corrections),
    onSuccess: (response, variables) => {
      setResults({
        runId: variables.runId,
        // The reader's own confidence, not the 1.0 the backend records once a line is confirmed.
        ocrConfidence: confirmation?.ocrConfidence ?? averageConfidence(response.data.items),
        items: response.data.items,
      });
      setStep('results');
    },
    onError: () => setErrorMessage('Could not save your corrections. Please try again.'),
  });

  function startOver() {
    setConfirmation(null);
    setResults(null);
    setPatientName(null);
    setErrorMessage(null);
    setIsPatientDialogOpen(false);
    setStep('upload');
  }

  return (
    <section aria-label="Prescription Analyzer">
      <PageHeader
        eyebrow="AI-assisted"
        title="Prescription & Medicine Analyzer"
        description="Upload a prescription or tablet strip and we'll read it, flag anything unclear, and surface doctor-reviewable generic alternatives with estimated savings."
        icon={<span aria-hidden="true">&#8478;</span>}
      />

      <div className={styles.steps}>
        <button
          type="button"
          className={styles.stepPill}
          data-active={step === 'upload'}
          onClick={startOver}
          disabled={step === 'upload'}
        >
          1. Upload
        </button>
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

      {isPatientDialogOpen && confirmation && (
        <PatientIdentityDialog
          runId={confirmation.runId}
          extractedName={patientName}
          onAssigned={() => {
            setIsPatientDialogOpen(false);
            setStep('confirm');
          }}
          onCancel={startOver}
        />
      )}

      {step === 'confirm' && confirmation && (
        <ConfirmStep
          items={confirmation.items}
          onSubmit={(corrections) => confirmMutation.mutate({ runId: confirmation.runId, corrections })}
          isPending={confirmMutation.isPending}
        />
      )}

      {step === 'results' && results && (
        <ResultsStep
          runId={results.runId}
          ocrConfidence={results.ocrConfidence}
          items={results.items}
          patientName={patientName}
          onStartOver={startOver}
        />
      )}
    </section>
  );
}
