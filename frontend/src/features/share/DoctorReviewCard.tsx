/**
 * "Send to a doctor" panel: pick registered clinicians, email them the review PDF, then track
 * their decision. Nothing is shown as approved until a clinician confirms it (FR5.3/FR5.6).
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge, Button, Card, ErrorState, LoadingState } from '@/components/ui';
import { ApiError } from '@/lib/apiClient';

import { fetchDoctors, fetchReviewStatus, requestReview } from './api';
import styles from './share.module.css';
import type { BadgeTone } from '@/components/ui';
import type { ReviewState, ReviewSummary } from './api';

const STATUS_COPY: Record<ReviewState, { label: string; tone: BadgeTone }> = {
  pending: { label: 'Waiting for the doctor', tone: 'info' },
  approved: { label: 'Approved', tone: 'success' },
  changes_requested: { label: 'Changes requested', tone: 'warning' },
  rejected: { label: 'Not approved', tone: 'danger' },
  expired: { label: 'Request expired', tone: 'neutral' },
};

interface DoctorReviewCardProps {
  runId: string;
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
      {review.notes && <blockquote className={styles.notes}>{review.notes}</blockquote>}
    </li>
  );
}

export function DoctorReviewCard({ runId }: DoctorReviewCardProps) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const doctorsQuery = useQuery({ queryKey: ['doctors'], queryFn: fetchDoctors, staleTime: 300_000 });

  const statusQuery = useQuery({
    queryKey: ['reviews', runId],
    queryFn: () => fetchReviewStatus(runId),
    // The doctor answers out of band from their inbox, so poll while anything is outstanding.
    refetchInterval: (query) =>
      query.state.data?.data.reviews.some((review) => review.status === 'pending') ? 5000 : false,
  });

  const sendMutation = useMutation({
    mutationFn: () => requestReview(runId, selected),
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

      {doctorsQuery.isLoading && <LoadingState message="Loading registered doctors..." />}
      {doctorsQuery.isError && (
        <ErrorState message="Could not load the doctor list." onRetry={() => doctorsQuery.refetch()} />
      )}

      {doctors.length > 0 && (
        <fieldset className={styles.doctorList}>
          <legend className={styles.legend}>Registered with Health IQ</legend>
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
        <Button
          onClick={() => sendMutation.mutate()}
          isLoading={sendMutation.isPending}
          disabled={selected.length === 0}
        >
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
