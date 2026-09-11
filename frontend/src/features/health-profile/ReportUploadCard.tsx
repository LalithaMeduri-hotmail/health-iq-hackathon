/**
 * Lab-report upload panel. Client-side type/size checks are UX hints only - the backend remains
 * the source of truth - and the consent note stays visible because analysis records consent.
 */

import { useRef, useState } from 'react';

import { Button, Card } from '@/components/ui';

import styles from './health-profile.module.css';

const ACCEPTED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.heic'];
const MAX_BYTES = 10 * 1024 * 1024;

interface ReportUploadCardProps {
  isPending: boolean;
  onAnalyze: (file: File) => void;
  onDismiss?: () => void;
}

function fileProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return 'Use a PDF, JPG, PNG, or HEIC file.';
  }
  if (file.size > MAX_BYTES) {
    return 'That file is larger than 10 MB. Try a smaller scan or export.';
  }
  return null;
}

function readableSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ReportUploadCard({ isPending, onAnalyze, onDismiss }: ReportUploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function accept(candidate: File | undefined) {
    if (!candidate) {
      return;
    }
    const issue = fileProblem(candidate);
    setProblem(issue);
    setFile(issue ? null : candidate);
  }

  return (
    <Card
      className={styles.card}
      title="Analyze a lab report"
      subtitle="PDF, JPG, PNG, or HEIC up to 10 MB. The report joins your history and refreshes every panel below."
      actions={
        onDismiss ? (
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            Close
          </Button>
        ) : undefined
      }
    >
      <div
        className={styles.dropzone}
        data-dragging={isDragging}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          accept(event.dataTransfer.files?.[0]);
        }}
      >
        <p className={styles.dropzoneHint}>Drag a report here, or</p>
        <Button variant={file ? 'secondary' : 'primary'} onClick={() => inputRef.current?.click()}>
          {file ? 'Choose a different file' : 'Choose a file'}
        </Button>
        <input
          ref={inputRef}
          id="profile-report-file"
          className="visually-hidden"
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          aria-label="Lab report file"
          onChange={(event) => accept(event.target.files?.[0])}
        />
        {file && (
          <p className={styles.fileChip}>
            {file.name} <span className={styles.source}>({readableSize(file.size)})</span>
          </p>
        )}
        {problem && (
          <p className={styles.fieldError} role="alert">
            {problem}
          </p>
        )}
      </div>

      <div className={styles.actions}>
        {file && (
          <Button onClick={() => onAnalyze(file)} isLoading={isPending}>
            Analyze report
          </Button>
        )}
        <p className={styles.source}>
          Uploading records your consent for OCR and analysis. Nothing is shared with anyone else.
        </p>
      </div>
    </Card>
  );
}
