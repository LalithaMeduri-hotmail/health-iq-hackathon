/**
 * "Send to a doctor" panel: pick registered clinicians, email them the review PDF, then track
 * their decision. Nothing is shown as approved until a clinician confirms it (FR5.3/FR5.6).
 */

import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge, Button, Card, ErrorState, Input, LoadingState } from '@/components/ui';
import { useAuth } from '@/features/auth';
import { ApiError } from '@/lib/apiClient';

import { fetchDoctors, fetchReviewStatus, requestReview, reviewDocumentUrl } from './api';
import styles from './share.module.css';
import type { BadgeTone } from '@/components/ui';
import type { PrescriptionKind, ReviewDecision, ReviewState, ReviewSummary } from './api';

const STATUS_COPY: Record<ReviewState, { label: string; tone: BadgeTone }> = {
  pending: { label: 'Waiting for the doctor', tone: 'info' },
  approved: { label: 'Approved', tone: 'success' },
  changes_requested: { label: 'Changes requested', tone: 'warning' },
  rejected: { label: 'Not approved', tone: 'danger' },
  expired: { label: 'Request expired', tone: 'neutral' },
};

const DECISION_COPY: Record<ReviewDecision, { label: string; tone: BadgeTone }> = {
  approved: { label: 'Approved', tone: 'success' },
  changes_requested: { label: 'Change requested', tone: 'warning' },
  rejected: { label: 'Not approved', tone: 'danger' },
};

const DOCUMENT_COPY: Record<PrescriptionKind, string> = {
  approved: 'New Health IQ prescription',
  followup: 'Follow-up required',
};

interface DoctorReviewCardProps {
  runId: string;
  /** Read off the uploaded prescription, when the reader found a name there. */
  detectedPatientName?: string | null;
}

/** Which of the two outcome documents this review actually produced. */
function documentKinds(review: ReviewSummary): PrescriptionKind[] {
  const verdicts = new Set(review.decisions.map((entry) => entry.decision));
  const kinds: PrescriptionKind[] = [];
  if (verdicts.has('approved')) {
    kinds.push('approved');
  }
  if (verdicts.has('changes_requested') || verdicts.has('rejected')) {
    kinds.push('followup');
  }
  return kinds;
}

function ReviewRow({ review }: { review: ReviewSummary }) {
  const status = STATUS_COPY[review.status] ?? STATUS_COPY.pending;
  return (
    <li className={styles.reviewRow}>
      <div className={styles.reviewHead}>
        <span className={styles.doctorName}>
          {review.doctorName} <span className={styles.specialty}>{review.doctorSpecialty}</span>
        </span>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <p className={styles.reviewMeta}>
        Sent to {review.doctorEmailMasked}
        {review.decidedAt ? ` · answered ${new Date(review.decidedAt).toLocaleString()}` : ''}
      </p>

      {review.decisions.length > 0 && (
        <ul className={styles.verdictList}>
          {review.decisions.map((verdict) => (
            <li key={verdict.lineId} className={styles.verdictRow}>
              <span>{verdict.label}</span>
              <Badge tone={DECISION_COPY[verdict.decision].tone}>
                {DECISION_COPY[verdict.decision].label}
              </Badge>
            </li>
          ))}
        </ul>
      )}

      {review.notes && <blockquote className={styles.notes}>{review.notes}</blockquote>}

      {documentKinds(review).length > 0 && (
        <p className={styles.documentRow}>
          {documentKinds(review).map((kind) => (
            <a
              key={kind}
              className={styles.documentLink}
              href={reviewDocumentUrl(review.reviewId, kind)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {DOCUMENT_COPY[kind]} (PDF)
            </a>
          ))}
        </p>
      )}
    </li>
  );
}

export function DoctorReviewCard({ runId, detectedPatientName }: DoctorReviewCardProps) {
  const queryClient = useQueryClient();
  const { account } = useAuth();
  const [selected, setSelected] = useState<string[]>([]);
  const [patientName, setPatientName] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  // The prescription is the source of truth for the name on the document; the account name is
  // only a fallback, and either way the patient confirms it before anything is sent.
  const suggestedName = detectedPatientName || account?.displayName || '';
  useEffect(() => {
    if (suggestedName) {
      setPatientName((current) => current || suggestedName);
    }
  }, [suggestedName]);

  const doctorsQuery = useQuery({ queryKey: ['doctors'], queryFn: fetchDoctors, staleTime: 300_000 });

  const statusQuery = useQuery({
    queryKey: ['reviews', runId],
    queryFn: () => fetchReviewStatus(runId),
    // The doctor answers out of band from their inbox, so poll while anything is outstanding.
    refetchInterval: (query) =>
      query.state.data?.data.reviews.some((review) => review.status === 'pending') ? 5000 : false,
  });

  const sendMutation = useMutation({
    mutationFn: () => requestReview(runId, selected, patientName.trim()),
    onSuccess: () => {
      setErrorMessage(null);
      setSelected([]);
      void queryClient.invalidateQueries({ queryKey: ['reviews', runId] });
    },
    onError: (error: unknown) =>
      setErrorMessage(
        error instanceof ApiError ? error.problem.detail : 'Could not send the review request.',
      ),
  });

  const doctors = doctorsQuery.data?.data.doctors ?? [];
  const reviews = statusQuery.data?.data.reviews ?? [];
  const isApproved = statusQuery.data?.data.approved ?? false;

  function toggle(doctorId: string) {
    setSelected((current) =>
      current.includes(doctorId) ? current.filter((id) => id !== doctorId) : [...current, doctorId],
    );
  }

  // Validating on submit rather than disabling the button, so the reason lands on the field the
  // user has to fix instead of next to a control they cannot press.
  function send() {
    if (patientName.trim().length === 0) {
      setNameError('Add the patient name before sending.');
      nameRef.current?.focus();
      return;
    }
    sendMutation.mutate();
  }

  return (
    <Card
      title="Send to a doctor for review"
      subtitle="We email the review PDF to the clinicians you pick. They confirm from their own inbox."
    >
      {isApproved && (
        <p className={styles.approvedBanner}>
          <Badge tone="success">Alternatives approved</Badge> A doctor has approved the equivalents in
          this summary. Keep following their instructions on when to switch.
        </p>
      )}

      {errorMessage && <ErrorState message={errorMessage} onRetry={() => setErrorMessage(null)} retryLabel="Dismiss" />}

      <Input
        ref={nameRef}
        label="Patient name"
        placeholder="e.g. Ramesh Kumar"
        value={patientName}
        onChange={(event) => {
          setPatientName(event.target.value);
          setNameError(null);
        }}
        error={nameError ?? undefined}
        hint={
          suggestedName
            ? 'We read this from your prescription - correct it if it is wrong.'
            : 'As it appears on your prescription. It goes on the document the doctor signs.'
        }
      />

      {doctorsQuery.isLoading && <LoadingState message="Loading registered doctors..." />}
      {doctorsQuery.isError && (
        <ErrorState message="Could not load the doctor list." onRetry={() => doctorsQuery.refetch()} />
      )}

      {doctors.length > 0 && (
        <fieldset className={styles.doctorList}>
          <legend className={styles.legend}>Send to</legend>
          {doctors.map((doctor) => (
            <label key={doctor.doctorId} className={styles.doctorOption}>
              <input
                type="checkbox"
                checked={selected.includes(doctor.doctorId)}
                onChange={() => toggle(doctor.doctorId)}
              />
              <span>
                <span className={styles.doctorName}>{doctor.name}</span>
                <span className={styles.reviewMeta}>
                  {doctor.specialty} · {doctor.emailMasked}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      )}

      <div className={styles.sendRow}>
        <p className={styles.sendNote}>
          {selected.length === 0
            ? 'Pick at least one doctor above.'
            : `We'll email ${selected.length === 1 ? 'this doctor' : `these ${selected.length} doctors`} the review PDF.`}
        </p>
        <Button onClick={send} isLoading={sendMutation.isPending} disabled={selected.length === 0}>
          Email the review request
        </Button>
      </div>

      {reviews.length > 0 && (
        <ul className={styles.reviewList}>
          {reviews.map((review) => (
            <ReviewRow key={review.reviewId} review={review} />
          ))}
        </ul>
      )}
    </Card>
  );
}
