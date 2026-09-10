/**
 * One expandable row of the report-history timeline. The detail request is lazy: it only fires
 * once the row is opened, so loading the profile stays a single call.
 */

import { useQuery } from '@tanstack/react-query';

import { Badge, ErrorState, LoadingState } from '@/components/ui';

import { ParameterTable } from './ParameterTable';
import { fetchReportDetail } from './api';
import { formatReportDate, scoreTone } from './status';
import styles from './health-profile.module.css';
import type { ProfileReportItem } from './types';

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
        <span className={styles.timelineDate}>{formatReportDate(report.reportDate)}</span>
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
              <h4 className={styles.panelHeading}>
                All {detail.parameters.length} results ({detail.abnormal.length} outside the typical range)
              </h4>
              <ParameterTable parameters={detail.parameters} />
            </>
          )}
        </div>
      )}
    </li>
  );
}
