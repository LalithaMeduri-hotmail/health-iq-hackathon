/**
 * Always-visible profile summary: the latest indicator score, how it moved since the previous
 * report, what drove it, and the consent/demographic context the rest of the page is based on.
 */

import { HealthScoreGauge } from '@/components/Charts';
import { Badge, Button, Card } from '@/components/ui';

import { formatReportDate } from './status';
import styles from './health-profile.module.css';
import type { Profile, ProfileReportItem, ReportDetailResponse } from './types';

interface ProfileSummaryProps {
  profile: Profile;
  reports: ProfileReportItem[];
  latestReportId: string | null;
  latestScore: number | null;
  latestDetail: ReportDetailResponse | null;
  /** Hidden while the upload panel is already on screen, so there is only ever one way in. */
  showAnalyzeAction: boolean;
  onAnalyzeClick: () => void;
}

function deltaCopy(delta: number): { label: string; tone: 'success' | 'warning' | 'neutral' } {
  if (delta === 0) {
    return { label: 'No change', tone: 'neutral' };
  }
  return delta > 0
    ? { label: `+${delta} points`, tone: 'success' }
    : { label: `${delta} points`, tone: 'warning' };
}

export function ProfileSummary({
  profile,
  reports,
  latestReportId,
  latestScore,
  latestDetail,
  showAnalyzeAction,
  onAnalyzeClick,
}: ProfileSummaryProps) {
  const latestIndex = reports.findIndex((report) => report.reportId === latestReportId);
  const latest = latestIndex >= 0 ? reports[latestIndex] : reports[0];
  const previous = latestIndex >= 0 ? reports[latestIndex + 1] : reports[1];
  const delta = latest && previous ? latest.healthScore - previous.healthScore : null;
  const demographics = [profile.demographics.ageBand, profile.demographics.sex, profile.demographics.location].filter(
    Boolean,
  );

  return (
    <Card className={styles.summary}>
      <div className={styles.summaryLayout}>
        <div className={styles.summaryGauge}>
          {latestScore === null ? (
            <div className={styles.gaugePlaceholder}>
              <span className={styles.gaugePlaceholderValue}>--</span>
              <span className={styles.meta}>No indicator score yet</span>
            </div>
          ) : (
            <HealthScoreGauge score={latestScore} reportDate={latest?.reportDate} />
          )}
        </div>

        <div className={styles.summaryBody}>
          <div className={styles.summaryHeading}>
            <div>
              <h2 className={styles.summaryTitle}>Health indicator score</h2>
              <p className={styles.meta}>
                A transparent, rule-based indicator built from your lab values - not a diagnosis.
              </p>
            </div>
            {showAnalyzeAction && (
              <Button variant="secondary" onClick={onAnalyzeClick}>
                Analyze new report
              </Button>
            )}
          </div>

          <dl className={styles.stats}>
            <div className={styles.stat}>
              <dt className={styles.statLabel}>Since previous report</dt>
              <dd className={styles.statValue}>
                {delta === null ? (
                  <span className={styles.statMuted}>Needs two reports</span>
                ) : (
                  <Badge tone={deltaCopy(delta).tone}>{deltaCopy(delta).label}</Badge>
                )}
              </dd>
            </div>

            <div className={styles.stat}>
              <dt className={styles.statLabel}>Outside typical range</dt>
              <dd className={styles.statValue}>
                {latestDetail ? (
                  <>
                    {latestDetail.abnormal.length}
                    <span className={styles.statMuted}> of {latestDetail.parameters.length} values</span>
                  </>
                ) : (
                  <span className={styles.statMuted}>--</span>
                )}
              </dd>
            </div>

            <div className={styles.stat}>
              <dt className={styles.statLabel}>Reports on record</dt>
              <dd className={styles.statValue}>{reports.length}</dd>
            </div>

            <div className={styles.stat}>
              <dt className={styles.statLabel}>Score from</dt>
              <dd className={styles.statValue}>
                {latest ? formatReportDate(latest.reportDate) : <span className={styles.statMuted}>--</span>}
              </dd>
            </div>
          </dl>

          <div className={styles.chips}>
            {profile.consent.version ? (
              <Badge tone="success">Consent v{profile.consent.version} accepted</Badge>
            ) : (
              <Badge tone="neutral">Consent captured on first analysis</Badge>
            )}
            {demographics.map((value) => (
              <Badge key={value} tone="info">
                {value}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
