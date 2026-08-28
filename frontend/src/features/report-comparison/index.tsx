/**
 * Report Comparison feature root (frontend.instructions.md colocation).
 *
 * TODO(D4): two-report picker (upload or history) -> color-coded before/after table -> line
 * chart per repeated parameter -> radar chart by system -> progression narrative.
 */

import { EmptyState, PageHeader } from '@/components/ui';

export function ReportComparisonFeature() {
  return (
    <section aria-label="Report Comparison">
      <PageHeader
        eyebrow="AI-assisted"
        title="Report Comparison Engine"
        description="See how your lab parameters have changed over time, with plain-language, sourced explanations."
        icon={<span aria-hidden="true">&#128202;</span>}
      />
      <EmptyState
        icon={<span aria-hidden="true">&#128202;</span>}
        title="Report Comparison is on its way"
        description="Pick two lab reports to see a color-coded before/after table, trend lines, and a plain-language progression summary - coming with Feature 3."
      />
    </section>
  );
}
