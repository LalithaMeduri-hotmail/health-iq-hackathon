/**
 * One expandable row of the report-history timeline. The detail request is lazy: it only fires
 * once the row is opened, so loading the profile stays a single call.
 */

import { useQuery } from '@tanstack/react-query';

import { Badge, ErrorState, LoadingState } from '@/components/ui';
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui';

import { fetchReportDetail } from './api';
import styles from './health-profile.module.css';
import type { BadgeTone } from '@/components/ui';
import type { LabParameter, ProfileReportItem } from './types';

const STATUS_TONES: Record<string, BadgeTone> = {
  high: 'danger',
  low: 'warning',
  critical_flag: 'danger',
  unknown: 'neutral',
};

const STATUS_LABELS: Record<string, string> = {
  high: 'Above range',
  low: 'Below range',
  critical_flag: 'Flagged',
  unknown: 'No range on file',
};

const RISK_TONES: Record<string, BadgeTone> = {
  typical: 'success',
  watch: 'warning',
  discuss: 'danger',
};

function scoreTone(score: number): BadgeTone {
  return score >= 80 ? 'success' : score >= 60 ? 'warning' : 'danger';
}

function range(parameter: LabParameter): string {
  if (parameter.refLow === null || parameter.refHigh === null) {
    return 'Not on file';
  }
  return `${parameter.refLow} - ${parameter.refHigh} ${parameter.unit}`;
}

interface ReportHistoryItemProps {
  report: ProfileReportItem;
  isLatest: boolean;
  isOpen: boolean;
  onToggle: () => void;
}

export function ReportHistoryItem({ report, isLatest, isOpen, onToggle }: ReportHistoryItemProps) {
  const panelId = `report-panel-${report.reportId}`;

  const detailQuery = useQuery({
    queryKey: ['report-detail', report.reportId],
    queryFn: () => fetchReportDetail(report.reportId),
    enabled: isOpen,
  });

  const detail = detailQuery.data?.data;

  return (
    <li className={styles.timelineItem}>
      <button
        type="button"
        className={styles.timelineHeader}
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className={styles.chevron} aria-hidden="true" data-open={isOpen}>
          &#9656;
        </span>
        <span className={styles.timelineDate}>{report.reportDate}</span>
        <span className={styles.timelineBadges}>
          <Badge tone={scoreTone(report.healthScore)}>Indicator score {report.healthScore}</Badge>
          {isLatest && <Badge tone="brand">Latest</Badge>}
        </span>
      </button>

      {isOpen && (
        <div className={styles.timelinePanel} id={panelId}>
          {detailQuery.isLoading && <LoadingState message="Loading this report..." />}

          {detailQuery.isError && (
            <ErrorState message="Could not load this report." onRetry={() => detailQuery.refetch()} />
          )}

          {detail && (
            <>
              <h4 className={styles.panelHeading}>Why the score is {detail.scoreBreakdown.healthScore}</h4>
              <p className={styles.meta}>{detail.scoreBreakdown.method}</p>
              <ul className={styles.penalties}>
                <li>
                  <span>Starting score</span>
                  <span className={styles.penaltyValue}>{detail.scoreBreakdown.baseScore}</span>
                </li>
                {detail.scoreBreakdown.penalties.map((penalty) => (
                  <li key={penalty.canonicalKey}>
                    <span>
                      {penalty.displayName}{' '}
                      <span className={styles.source}>({STATUS_LABELS[penalty.status] ?? penalty.status})</span>
                    </span>
                    <span className={styles.penaltyValue}>-{penalty.penalty}</span>
                  </li>
                ))}
                <li className={styles.penaltyTotal}>
                  <span>Indicator score</span>
                  <span className={styles.penaltyValue}>{detail.scoreBreakdown.healthScore} / 100</span>
                </li>
              </ul>

              <h4 className={styles.panelHeading}>
                Outside the typical range ({detail.abnormal.length} of {detail.parameters.length})
              </h4>
              {detail.abnormal.length === 0 ? (
                <p className={styles.meta}>Every measured value sits inside its typical range.</p>
              ) : (
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell scope="col">Parameter</TableHeaderCell>
                      <TableHeaderCell scope="col">Value</TableHeaderCell>
                      <TableHeaderCell scope="col">Typical range</TableHeaderCell>
                      <TableHeaderCell scope="col">Status</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detail.abnormal.map((parameter) => (
                      <TableRow key={parameter.canonicalKey}>
                        <TableCell>{parameter.displayName}</TableCell>
                        <TableCell>
                          {parameter.value} {parameter.unit}
                        </TableCell>
                        <TableCell>{range(parameter)}</TableCell>
                        <TableCell>
                          <Badge tone={STATUS_TONES[parameter.status] ?? 'neutral'}>
                            {STATUS_LABELS[parameter.status] ?? parameter.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}

              {detail.systemCards.length > 0 && (
                <>
                  <h4 className={styles.panelHeading}>By organ and system</h4>
                  <div className={styles.chips}>
                    {detail.systemCards.map((card) => (
                      <Badge key={card.system} tone={RISK_TONES[card.riskLevel] ?? 'neutral'}>
                        {card.system}: {card.riskLevel}
                      </Badge>
                    ))}
                  </div>
                </>
              )}

              <p className={styles.narrative}>{detail.narrative}</p>
            </>
          )}
        </div>
      )}
    </li>
  );
}
