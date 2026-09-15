/**
 * Step 3: confirmed medicines + doctor-reviewable alternatives (savings badges, doctor-approval
 * ribbon, source/date provenance - frontend.instructions.md safety UX requirements).
 */

import { useQuery } from '@tanstack/react-query';

import { Badge, Button, Card, LoadingState } from '@/components/ui';
import { DoctorReviewCard } from '@/features/share/DoctorReviewCard';
import { fetchReviewStatus } from '@/features/share/api';

import { fetchAlternatives } from './api';
import styles from './prescription.module.css';
import type { AlternativeMedicine, MedicineEntity } from './types';

interface ResultsStepProps {
  runId: string;
  ocrConfidence: number;
  items: MedicineEntity[];
  patientName: string | null;
  onStartOver: () => void;
}

function AlternativeCard({ alternative, isApproved }: { alternative: AlternativeMedicine; isApproved: boolean }) {
  return (
    <div className={styles.altCard}>
      <div className={styles.altHeadline}>
        <span className={styles.altName}>
          {alternative.generic} <span style={{ fontWeight: 400 }}>({alternative.cheaper})</span>
        </span>
        <Badge tone="success">Save {alternative.savingsPct}%</Badge>
      </div>
      <p className={styles.altPrice}>
        MRP &#8377;{alternative.originalMrpInr.toFixed(2)} &rarr; &#8377;{alternative.cheaperMrpInr.toFixed(2)}{' '}
        (estimated)
      </p>
      <div className={styles.altFooter}>
        {isApproved ? (
          <Badge tone="success">Approved by your doctor</Badge>
        ) : (
          <Badge tone="warning">Doctor approval required before switching</Badge>
        )}
        <span className={styles.source}>
          Source: {alternative.source.sourceName} &middot; {alternative.source.sourceDate}
        </span>
      </div>
    </div>
  );
}

function MedicineAlternatives({ item, isApproved }: { item: MedicineEntity; isApproved: boolean }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['medicine-alternatives', item.lineId, item.activeIngredient, item.strengthValue, item.dosageForm],
    queryFn: () => fetchAlternatives([item]),
    enabled: Boolean(item.activeIngredient && item.strengthValue && item.dosageForm),
  });

  if (!item.activeIngredient) {
    return <p>Not enough information to look up alternatives for this line.</p>;
  }
  if (isLoading) {
    return <LoadingState message="Looking for doctor-reviewable alternatives..." />;
  }
  if (isError || !data) {
    return <p>Could not load alternatives right now.</p>;
  }
  if (data.data.alternatives.length === 0) {
    return <p>No safe alternative meets our matching rules yet.</p>;
  }

  return (
    <>
      {data.data.alternatives.map((alternative) => (
        <AlternativeCard key={alternative.cheaper} alternative={alternative} isApproved={isApproved} />
      ))}
    </>
  );
}

export function ResultsStep({ runId, ocrConfidence, items, patientName, onStartOver }: ResultsStepProps) {
  const reviewQuery = useQuery({ queryKey: ['reviews', runId], queryFn: () => fetchReviewStatus(runId) });
  const isApproved = reviewQuery.data?.data.approved ?? false;

  return (
    <div>
      <Card
        className={styles.resultHeader}
        title="Your medicines"
        subtitle={`OCR confidence ${(ocrConfidence * 100).toFixed(0)}%`}
        actions={
          <Button variant="secondary" size="sm" onClick={onStartOver}>
            Analyze another prescription
          </Button>
        }
      />

      {items.map((item) => (
        <Card key={item.lineId} className={styles.resultCard}>
          <h3>
            {item.brandName ?? item.rawText}
            {item.strengthValue ? ` ${item.strengthValue}${item.strengthUnit ?? ''}` : ''}
          </h3>
          {(item.frequency || item.duration) && (
            <p className={styles.resultMeta}>
              {[item.frequency, item.duration].filter(Boolean).join(' \u00b7 ')}
            </p>
          )}
          <MedicineAlternatives item={item} isApproved={isApproved} />
        </Card>
      ))}

      <div className={styles.shareBlock}>
        <DoctorReviewCard runId={runId} detectedPatientName={patientName} />
      </div>
    </div>
  );
}
