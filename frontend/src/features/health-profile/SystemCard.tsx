/**
 * One body-system tile. Collapsed it shows the risk level; expanded it answers the questions a
 * reader actually has - which specialist to see, what is off, and what is fine.
 */

import { Badge } from '@/components/ui';

import { ParameterList } from './ParameterList';
import { confidenceLabel, riskLabel, riskTone } from './status';
import styles from './health-profile.module.css';
import type { DoctorLink, LabParameter, SpecialistCategory, SystemCard as SystemCardData } from './types';

interface SystemCardProps {
  card: SystemCardData;
  outOfRange: LabParameter[];
  inRange: LabParameter[];
  specialist: SpecialistCategory | null;
  doctorLink: DoctorLink | null;
  disclaimer: string | null;
  isOpen: boolean;
  onToggle: () => void;
}

export function SystemCard({
  card,
  outOfRange,
  inRange,
  specialist,
  doctorLink,
  disclaimer,
  isOpen,
  onToggle,
}: SystemCardProps) {
  const panelId = `system-panel-${card.system.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <div className={styles.systemCard} data-risk={card.riskLevel} data-open={isOpen}>
      <button
        type="button"
        className={styles.systemButton}
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className={styles.systemHead}>
          <span className={styles.systemName}>{card.system}</span>
          <span className={styles.systemBadge}>
            <Badge tone={riskTone(card.riskLevel)}>{riskLabel(card.riskLevel)}</Badge>
          </span>
        </span>
        <span className={styles.systemCounts}>
          {outOfRange.length === 0
            ? `All ${inRange.length} in range`
            : `${outOfRange.length} outside range${inRange.length > 0 ? ` \u00b7 ${inRange.length} in range` : ''}`}
        </span>
        <span className={styles.systemCue}>
          {isOpen ? 'Hide details' : 'Tap to see who to consult'}
          <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`} aria-hidden="true" />
        </span>
      </button>

      {isOpen && (
        <div className={styles.systemPanel} id={panelId}>
          {specialist ? (
            <div className={styles.specialist}>
              <span className={styles.specialistIcon} aria-hidden="true">
                &#129658;
              </span>
              <div className={styles.specialistBody}>
                <p className={styles.evidenceLabel}>Who to consult</p>
                <div className={styles.categoryHead}>
                  <h4 className={styles.categoryName}>{specialist.specialtyCategory}</h4>
                  <Badge tone="neutral">{confidenceLabel(specialist.confidence)}</Badge>
                </div>
                <p className={styles.specialistWhen}>{specialist.whenToConsult}</p>
                <p className={styles.source}>
                  {disclaimer ?? 'Specialty category suggestion only; not a diagnosis or urgency claim.'}{' '}
                  <a
                    href={specialist.source.sourceUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    title={`${specialist.source.sourceName} (${specialist.source.sourceDate})`}
                  >
                    Source
                  </a>
                  {doctorLink && (
                    <>
                      {' \u00b7 '}
                      <a href={doctorLink.url} target="_blank" rel="noreferrer noopener" title={doctorLink.name}>
                        Find a doctor
                      </a>
                    </>
                  )}
                </p>
              </div>
            </div>
          ) : (
            <p className={styles.meta}>
              Everything measured here sits inside its typical range, so no specialty stands out. A general
              physician can read it in context.
            </p>
          )}

          {outOfRange.length > 0 && (
            <>
              <p className={styles.evidenceLabel}>Outside the typical range ({outOfRange.length})</p>
              <ParameterList parameters={outOfRange} />
            </>
          )}

          {inRange.length > 0 && (
            <>
              <p className={styles.evidenceLabel}>Within the typical range ({inRange.length})</p>
              <ul className={styles.inRangeList}>
                {inRange.map((parameter) => (
                  <li key={parameter.canonicalKey} className={styles.inRangeItem}>
                    <span className={styles.inRangeRow}>
                      <span className={styles.inRangeName}>{parameter.displayName}</span>
                      <span className={styles.inRangeValue}>
                        {parameter.value} {parameter.unit}
                      </span>
                    </span>
                    {parameter.meaning && <span className={styles.parameterMeaning}>{parameter.meaning}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
