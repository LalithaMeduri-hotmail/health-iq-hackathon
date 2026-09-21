/**
 * Health IQ prescriptions already issued for one profile, newest first.
 *
 * Every row is a stored snapshot of what the clinician approved, including the prices they saw,
 * so this deliberately does not re-price anything against today's catalog.
 */

import { useQuery } from '@tanstack/react-query';

import { Badge, Card, EmptyState, ErrorState, LoadingState } from '@/components/ui';

import { fetchIssuedPrescriptions, issuedPrescriptionPdfUrl } from './api';
import styles from './patientProfiles.module.css';
import type { BadgeTone } from '@/components/ui';
import type { IssuedPrescription, PrescriptionDecision } from './types';

const DECISION_COPY: Record<PrescriptionDecision, { label: string; tone: BadgeTone }> = {
  approved: { label: 'Approved', tone: 'success' },
  changes_requested: { label: 'Change requested', tone: 'warning' },
  rejected: { label: 'Not approved', tone: 'danger' },
};

function rupees(value: number): string {
  return `\u20b9${value.toFixed(2)}`;
}

function IssuedCard({ prescription }: { prescription: IssuedPrescription }) {
  const { document: doc } = prescription;
  return (
    <Card className={styles.rxCard}>
      <div className={styles.rxHead}>
        <div>
          <span className={styles.rxDoctor}>{doc.doctorName}</span>
          <span className={styles.rxMeta}>
            {doc.doctorSpecialty} &middot; reviewed {doc.reviewedAt}
          </span>
        </div>
        <span className={styles.rxMeta}>Ref {doc.reference}</span>
      </div>

      <div className={styles.rxTableWrap}>
        <table className={styles.rxTable}>
          <thead>
            <tr>
              <th scope="col">Medicine</th>
              <th scope="col">Approved alternative</th>
              <th scope="col">Decision</th>
            </tr>
          </thead>
          <tbody>
            {doc.lines.map((line) => (
              <tr key={`${prescription.id}-${line.label}`}>
                <td>
                  <span className={styles.rxName}>{line.label}</span>
                  {line.maker && <span className={styles.rxMeta}>{line.maker}</span>}
                </td>
                <td>
                  {line.alternative ? (
                    <>
                      <span className={styles.rxName}>{line.alternative}</span>
                      {line.alternativeMaker && (
                        <span className={styles.rxMeta}>{line.alternativeMaker}</span>
                      )}
                      {line.originalMrpInr > 0 && line.cheaperMrpInr > 0 && (
                        <span className={styles.rxMeta}>
                          {rupees(line.originalMrpInr)} &rarr; {rupees(line.cheaperMrpInr)}
                          {line.savingsPct > 0 ? ` \u00b7 about ${line.savingsPct}% less` : ''}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className={styles.rxMeta}>No equivalent proposed</span>
                  )}
                </td>
                <td>
                  <Badge tone={DECISION_COPY[line.decision].tone}>
                    {DECISION_COPY[line.decision].label}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {doc.notes && <blockquote className={styles.rxNotes}>{doc.notes}</blockquote>}

      <p className={styles.rxActions}>
        <a
          className={styles.rxLink}
          href={issuedPrescriptionPdfUrl(prescription.profileId, prescription.id)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open prescription (PDF)
        </a>
      </p>
    </Card>
  );
}

export function PrescriptionHistory({
  profileId,
  profileName,
}: {
  profileId: string;
  profileName: string;
}) {
  const query = useQuery({
    queryKey: ['issued-prescriptions', profileId],
    queryFn: () => fetchIssuedPrescriptions(profileId),
  });

  if (query.isLoading) {
    return <LoadingState message="Loading prescription history..." />;
  }
  if (query.isError) {
    return (
      <ErrorState
        message="Could not load the prescription history."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const prescriptions = query.data?.data.prescriptions ?? [];
  if (prescriptions.length === 0) {
    return (
      <EmptyState
        title="No Health IQ prescriptions yet"
        description={`Once a doctor reviews a prescription for ${profileName}, the approved result is kept here for future checks.`}
      />
    );
  }

  return (
    <div className={styles.rxList}>
      {prescriptions.map((prescription) => (
        <IssuedCard key={prescription.id} prescription={prescription} />
      ))}
    </div>
  );
}
