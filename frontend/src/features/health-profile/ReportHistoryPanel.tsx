/** Reports tab: every report on record, newest first, with its values available on demand. */

import { Card, EmptyState } from '@/components/ui';

import { ReportHistoryItem } from './ReportHistoryItem';
import styles from './health-profile.module.css';
import type { ProfileReportItem } from './types';

interface ReportHistoryPanelProps {
  reports: ProfileReportItem[];
  latestReportId: string | null;
  openReportId: string | null;
  onToggleReport: (reportId: string) => void;
}

export function ReportHistoryPanel({
  reports,
  latestReportId,
  openReportId,
  onToggleReport,
}: ReportHistoryPanelProps) {
  return (
    <Card
      title="Report history"
      subtitle="Every report you have analyzed, newest first. Open one to see its full results table."
    >
      {reports.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden="true">&#128203;</span>}
          title="No reports yet"
          description="Analyze a lab report above and it will appear here as a timeline you can compare against."
        />
      ) : (
        <ul className={styles.timeline}>
          {reports.map((report) => (
            <ReportHistoryItem
              key={report.reportId}
              report={report}
              isLatest={report.reportId === latestReportId}
              isOpen={openReportId === report.reportId}
              onToggle={() => onToggleReport(report.reportId)}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}
