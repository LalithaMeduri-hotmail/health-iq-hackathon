/**
 * "Save or share it yourself" panel: build the doctor-review PDF, download it to this machine,
 * and hand out a revocable link for a clinician who is not registered with Health IQ.
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Badge, Button, Card, ErrorState } from '@/components/ui';
import { ApiError, absoluteApiUrl } from '@/lib/apiClient';

import { generateSharePdf, revokeShareLink } from './api';
import styles from './share.module.css';
import type { PdfGenerateResponse } from './api';

interface DoctorPdfCardProps {
  runId: string;
  /** Describes what the generated PDF contains, so each feature can be specific. */
  subtitle: string;
}

function describe(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) {
    return fallback;
  }
  // The safety reviewer returns its failing rules in `errors[]`; the bare title is not actionable.
  const reasons = error.problem.errors?.map((entry) => entry.issue).join('; ');
  return reasons ? `${error.problem.detail} (${reasons})` : error.problem.detail;
}

export function DoctorPdfCard({ runId, subtitle }: DoctorPdfCardProps) {
  const [share, setShare] = useState<PdfGenerateResponse | null>(null);
  const [isRevoked, setIsRevoked] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: () => generateSharePdf(runId),
    onSuccess: (response) => {
      setErrorMessage(null);
      setIsRevoked(false);
      setIsCopied(false);
      setShare(response.data);
    },
    onError: (error: unknown) => setErrorMessage(describe(error, 'Could not build the doctor PDF right now.')),
  });

  const revokeMutation = useMutation({
    mutationFn: (shareId: string) => revokeShareLink(shareId),
    onSuccess: () => {
      setErrorMessage(null);
      setIsRevoked(true);
    },
    onError: (error: unknown) => setErrorMessage(describe(error, 'Could not revoke that link. Please try again.')),
  });

  const shareUrl = share ? absoluteApiUrl(share.shareUrl) : '';

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setIsCopied(true);
    } catch {
      setErrorMessage('Could not copy automatically. Select the link below and copy it manually.');
    }
  }

  return (
    <Card
      title="Save or share it yourself"
      subtitle={subtitle}
      actions={
        <Button variant="secondary" onClick={() => generateMutation.mutate()} isLoading={generateMutation.isPending}>
          {share ? 'Rebuild the PDF' : 'Create doctor PDF'}
        </Button>
      }
    >
      {errorMessage && <ErrorState message={errorMessage} onRetry={() => setErrorMessage(null)} retryLabel="Dismiss" />}

      {!share && (
        <p>
          Builds the same review document we email to your registered doctors. Keep a copy on this device,
          or pass a link to a clinician who is not on Health IQ.
        </p>
      )}

      {share && isRevoked && (
        <p className={styles.revoked}>
          <Badge tone="neutral">Link revoked</Badge> That link no longer opens. Any copy you already
          downloaded is unaffected. Rebuild the PDF to hand out a new link.
        </p>
      )}

      {share && !isRevoked && (
        <>
          <div className={styles.option}>
            <div>
              <p className={styles.optionTitle}>Keep a copy</p>
              <p className={styles.optionHint}>Saves the PDF to this device. Nothing is shared.</p>
            </div>
            <a className={styles.downloadLink} href={`${shareUrl}?download=1`} download>
              Download PDF
            </a>
          </div>

          <div className={styles.option}>
            <div>
              <p className={styles.optionTitle}>Send to an outside doctor</p>
              <p className={styles.optionHint}>
                Expires {new Date(share.expiresAt).toLocaleString()}. Anyone holding the link can open the
                document until then, so send it only to your clinician.
              </p>
            </div>
            <div className={styles.optionActions}>
              <Button variant="secondary" size="sm" onClick={copyLink}>
                {isCopied ? 'Copied' : 'Copy link'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => revokeMutation.mutate(share.shareId)}
                isLoading={revokeMutation.isPending}
              >
                Revoke
              </Button>
            </div>
          </div>

          <p className={styles.linkPreview}>
            <a href={shareUrl} target="_blank" rel="noreferrer noopener">
              {shareUrl}
            </a>
          </p>
        </>
      )}
    </Card>
  );
}
