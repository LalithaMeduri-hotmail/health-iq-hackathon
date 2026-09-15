/**
 * Step 1: upload a prescription image/PDF or enter medicines manually (FR1.1).
 * Manual entry is the accessible fallback when OCR/camera capture is unavailable (NFR1.6).
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Button, Card, Combobox } from '@/components/ui';

import { fetchMedicineCatalog } from './api';
import styles from './prescription.module.css';

interface UploadStepProps {
  onSubmit: (input: { file?: File; manualMedicines?: string[] }) => void;
  isPending: boolean;
}

export function UploadStep({ onSubmit, isPending }: UploadStepProps) {
  const [file, setFile] = useState<File | null>(null);
  const [manualLines, setManualLines] = useState<string[]>(['']);
  // Which path was submitted, so only that button shows the spinner.
  const [submittedPath, setSubmittedPath] = useState<'file' | 'manual' | null>(null);

  const catalogQuery = useQuery({
    queryKey: ['medicine-catalog'],
    queryFn: fetchMedicineCatalog,
    staleTime: Infinity,
  });
  const catalogOptions = catalogQuery.data?.data.items.map((item) => item.label) ?? [];

  const cleanedManualLines = manualLines.map((line) => line.trim()).filter(Boolean);

  function submit(path: 'file' | 'manual') {
    setSubmittedPath(path);
    onSubmit(path === 'file' ? { file: file ?? undefined } : { manualMedicines: cleanedManualLines });
  }

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

      <div className={styles.actions}>
        <Button
          type="button"
          size="lg"
          disabled={!file}
          isLoading={isPending && submittedPath === 'file'}
          onClick={() => submit('file')}
        >
          Analyze prescription
        </Button>
      </div>

      <div className={styles.divider}>or enter medicines manually</div>

      {manualLines.map((line, index) => (
        <div className={styles.manualRow} key={index}>
          <Combobox
            label={`Medicine ${index + 1}`}
            options={catalogOptions}
            value={line ? [line] : []}
            onChange={(next) => {
              const updated = [...manualLines];
              updated[index] = next[0] ?? '';
              setManualLines(updated);
            }}
            placeholder={catalogQuery.isPending ? 'Loading medicines...' : 'Start typing, e.g. Gly'}
            hint={
              catalogQuery.isError
                ? undefined
                : 'Type a letter or two and pick from the list - only medicines in our catalog can be analyzed.'
            }
            error={catalogQuery.isError ? 'Could not load the medicine list. Please retry or upload your prescription instead.' : undefined}
          />
        </div>
      ))}
      <div className={styles.addRow}>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={manualLines.some((line) => !line)}
          onClick={() => setManualLines([...manualLines, ''])}
        >
          + Add another medicine
        </Button>
      </div>

      <div className={styles.actions}>
        <Button
          type="button"
          size="lg"
          disabled={cleanedManualLines.length === 0}
          isLoading={isPending && submittedPath === 'manual'}
          onClick={() => submit('manual')}
        >
          Find alternate medicines
        </Button>
      </div>
    </Card>
  );
}
