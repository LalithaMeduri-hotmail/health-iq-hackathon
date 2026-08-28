/**
 * Step 1: upload a prescription image/PDF or enter medicines manually (FR1.1).
 * Manual entry is the accessible fallback when OCR/camera capture is unavailable (NFR1.6).
 */

import { useState } from 'react';

import { Button, Card, Input } from '@/components/ui';

import styles from './prescription.module.css';

interface UploadStepProps {
  onSubmit: (input: { file?: File; manualMedicines?: string[] }) => void;
  isPending: boolean;
}

export function UploadStep({ onSubmit, isPending }: UploadStepProps) {
  const [file, setFile] = useState<File | null>(null);
  const [manualLines, setManualLines] = useState<string[]>(['']);

  const cleanedManualLines = manualLines.map((line) => line.trim()).filter(Boolean);
  const canSubmit = Boolean(file) || cleanedManualLines.length > 0;

  return (
    <Card
      title="Upload your prescription"
      subtitle="Upload a photo or PDF of your prescription or tablet strip. We only use this to read medicine names, strengths, and frequency - never to diagnose or change your treatment."
    >
      <label className={styles.dropzone} htmlFor="rx-file-input">
        {file ? `Selected: ${file.name}` : 'Tap to choose a photo or PDF (.jpg, .jpeg, .png, .pdf, .heic - max 10 MB)'}
      </label>
      <input
        id="rx-file-input"
        type="file"
        accept=".jpg,.jpeg,.png,.pdf,.heic"
        className="visually-hidden"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />

      <div className={styles.divider}>or enter medicines manually</div>

      {manualLines.map((line, index) => (
        <div className={styles.manualRow} key={index}>
          <Input
            label={`Medicine ${index + 1}`}
            placeholder="e.g. Glycomet 500mg 1-0-1 x10 days"
            value={line}
            onChange={(event) => {
              const next = [...manualLines];
              next[index] = event.target.value;
              setManualLines(next);
            }}
          />
        </div>
      ))}
      <div className={styles.addRow}>
        <Button type="button" variant="secondary" size="sm" onClick={() => setManualLines([...manualLines, ''])}>
          + Add another medicine
        </Button>
      </div>

      <div className={styles.actions}>
        <Button
          type="button"
          size="lg"
          disabled={!canSubmit}
          isLoading={isPending}
          onClick={() => onSubmit({ file: file ?? undefined, manualMedicines: cleanedManualLines })}
        >
          Analyze prescription
        </Button>
      </div>
    </Card>
  );
}
