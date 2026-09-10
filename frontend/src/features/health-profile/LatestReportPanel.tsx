/** Overview tab: what stood out, then a body-system grid that opens to its specialty and values. */

import { useState } from 'react';

import { Card, EmptyState, ErrorState, LoadingState } from '@/components/ui';

import { ParameterList } from './ParameterList';
import { SystemCard } from './SystemCard';
import { formatReportDate } from './status';
import styles from './health-profile.module.css';
import type { ReportDetailResponse, SpecialistCategory, SpecialistGuidance } from './types';

interface LatestReportPanelProps {
  detail: ReportDetailResponse | null;
  guidance: SpecialistGuidance | null;
  isSuppressed: boolean;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

/** The highest-ranked category whose triggering parameters overlap this system. */
function specialistFor(keys: string[], guidance: SpecialistGuidance | null): SpecialistCategory | null {
  return (
    guidance?.categories.find((category) =>
      category.parameters.some((parameter) => keys.includes(parameter.canonicalKey)),
    ) ?? null
  );
}

export function LatestReportPanel({
  detail,
  guidance,
  isSuppressed,
  isLoading,
  isError,
  onRetry,
}: LatestReportPanelProps) {
  const [openSystem, setOpenSystem] = useState<string | null>(null);

  if (isLoading) {
    return <LoadingState message="Loading your latest report..." />;
  }

  if (isError) {
    return <ErrorState message="Could not load your latest report." onRetry={onRetry} />;
  }

  if (!detail) {
    return (
      <EmptyState
        icon={<span aria-hidden="true">&#129514;</span>}
        title="No report analyzed yet"
        description="Upload a lab report above and this tab will explain what each value means, system by system."
      />
    );
  }

  return (
    <>
      <Card
        title={`What stood out (${detail.abnormal.length} of ${detail.parameters.length} values)`}
        subtitle={`From your report dated ${formatReportDate(detail.reportDate)}. These are worth raising with your doctor - they are not a diagnosis.`}
      >
        <ParameterList parameters={detail.abnormal} />
      </Card>

      <Card
        className={styles.card}
        title="Body systems at a glance"
        subtitle="Open a system to see who to consult and which values sit inside or outside the typical range."
      >
        {isSuppressed && (
          <ErrorState message="Specialty suggestions were withheld by the safety reviewer and cannot be shown." />
        )}

        <div className={styles.systemGrid}>
          {detail.systemCards.map((card) => {
            const measured = detail.parameters.filter((parameter) =>
              card.parameters.includes(parameter.canonicalKey),
            );
            const abnormalKeys = detail.abnormal.map((parameter) => parameter.canonicalKey);

            return (
              <SystemCard
                key={card.system}
                card={card}
                outOfRange={measured.filter((parameter) => abnormalKeys.includes(parameter.canonicalKey))}
                inRange={measured.filter((parameter) => !abnormalKeys.includes(parameter.canonicalKey))}
                specialist={specialistFor(card.parameters, guidance)}
                doctorLink={guidance?.doctorLinks[0] ?? null}
                disclaimer={guidance?.disclaimer ?? null}
                isOpen={openSystem === card.system}
                onToggle={() => setOpenSystem((current) => (current === card.system ? null : card.system))}
              />
            );
          })}
        </div>
      </Card>
    </>
  );
}
