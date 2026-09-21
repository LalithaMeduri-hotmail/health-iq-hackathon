/**
 * Step 3: confirmed medicines + doctor-reviewable alternatives (savings badges, doctor-approval
 * ribbon, source/date provenance - frontend.instructions.md safety UX requirements).
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Badge, Button, Card, LoadingState } from '@/components/ui';
import { DoctorReviewCard } from '@/features/share/DoctorReviewCard';
import { fetchReviewStatus } from '@/features/share/api';

import { fetchAlternatives } from './api';
import { MedicineArt } from './MedicineArt';
import styles from './prescription.module.css';
import type { AlternativeMedicine, MedicineEntity } from './types';

interface ResultsStepProps {
  runId: string;
  ocrConfidence: number;
  items: MedicineEntity[];
  patientName: string | null;
  onStartOver: () => void;
}

interface ComparisonCardProps {
  title: string;
  maker: string;
  mrp: number;
  dosageForm: string;
  isCurrent?: boolean;
  isSelected?: boolean;
  savingsPct?: number;
  isApproved?: boolean;
  source?: AlternativeMedicine['source'];
  onSelect?: () => void;
}

function ComparisonCard({
  title,
  maker,
  mrp,
  dosageForm,
  isCurrent = false,
  isSelected = false,
  savingsPct,
  isApproved,
  source,
  onSelect,
}: ComparisonCardProps) {
  const classes = [
    styles.compCard,
    isCurrent ? styles.compCardCurrent : styles.compCardAlt,
    isSelected ? styles.compCardSelected : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={classes}
      role={isCurrent ? undefined : 'radio'}
      aria-checked={isCurrent ? undefined : isSelected}
      tabIndex={isCurrent ? undefined : 0}
      onClick={isCurrent ? undefined : onSelect}
      onKeyDown={
        isCurrent
          ? undefined
          : (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onSelect?.();
              }
            }
      }
    >
      <div className={isCurrent ? styles.compTag : styles.compBanner}>
        {isCurrent ? 'Currently viewing' : `Save ${savingsPct}% \u2193`}
      </div>
      <MedicineArt seed={`${title}-${maker}`} dosageForm={dosageForm} className={styles.compArt} />
      <h4 className={styles.compTitle}>{title}</h4>
      <p className={styles.compMrp}>&#8377;{mrp.toFixed(2)}</p>
      {maker && <p className={styles.compMaker}>by {maker}</p>}
      {!isCurrent && (
        <>
          {isApproved ? (
            <Badge tone="success">Approved by your doctor</Badge>
          ) : (
            <Badge tone="warning">Doctor approval required</Badge>
          )}
          <button type="button" className={styles.compSelectBtn} onClick={(event) => event.stopPropagation()}>
            {isSelected ? 'Selected \u2713' : 'Select'}
          </button>
        </>
      )}
      {source && (
        <p className={styles.compSource}>
          Source: {source.sourceName} &middot; {source.sourceDate}
        </p>
      )}
    </div>
  );
}

function MedicineAlternatives({
  item,
  isApproved,
  selected,
  onSelect,
}: {
  item: MedicineEntity;
  isApproved: boolean;
  selected: string | null;
  onSelect: (cheaperBrand: string) => void;
}) {
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
  const alternatives = data.data.alternatives;
  if (alternatives.length === 0) {
    return <p>No safe alternative meets our matching rules yet.</p>;
  }

  const current = alternatives[0];

  return (
    <div className={styles.comparisonRow}>
      <ComparisonCard
        isCurrent
        title={current.original}
        maker={current.originalMaker}
        mrp={current.originalMrpInr}
        dosageForm={current.dosageForm}
      />
      {alternatives.map((alternative) => (
        <ComparisonCard
          key={alternative.cheaper}
          title={alternative.cheaperBrand}
          maker={alternative.manufacturer}
          mrp={alternative.cheaperMrpInr}
          dosageForm={alternative.dosageForm}
          savingsPct={alternative.savingsPct}
          isApproved={isApproved}
          source={alternative.source}
          isSelected={selected === alternative.cheaperBrand}
          onSelect={() => onSelect(alternative.cheaperBrand)}
        />
      ))}
    </div>
  );
}

export function ResultsStep({ runId, ocrConfidence, items, patientName, onStartOver }: ResultsStepProps) {
  const reviewQuery = useQuery({ queryKey: ['reviews', runId], queryFn: () => fetchReviewStatus(runId) });
  const isApproved = reviewQuery.data?.data.approved ?? false;
  // `lineId -> cheaperBrand`; this is what the doctor is asked to rule on, so it lives here
  // rather than inside each medicine card.
  const [selections, setSelections] = useState<Record<string, string>>({});

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
          <MedicineAlternatives
            item={item}
            isApproved={isApproved}
            selected={selections[item.lineId] ?? null}
            onSelect={(cheaperBrand) =>
              setSelections((current) => ({ ...current, [item.lineId]: cheaperBrand }))
            }
          />
        </Card>
      ))}

      <div className={styles.shareBlock}>
        <DoctorReviewCard
          runId={runId}
          detectedPatientName={patientName}
          selections={selections}
        />
      </div>
    </div>
  );
}
