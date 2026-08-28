/**
 * Health Profile feature root (frontend.instructions.md colocation).
 *
 * TODO(D4): demographics + preferences form, consent status, report history timeline,
 * health score gauge, organ/system cards with risk chips, specialist suggestion panel.
 */

import { EmptyState, PageHeader } from '@/components/ui';

export function HealthProfileFeature() {
  return (
    <section aria-label="Health Profile">
      <PageHeader
        eyebrow="AI-assisted"
        title="Health Profile & Specialist Advisor"
        description="Your demographics, consent status, report history, and specialist suggestions will live here."
        icon={<span aria-hidden="true">&#128100;</span>}
      />
      <EmptyState
        icon={<span aria-hidden="true">&#128100;</span>}
        title="Health Profile is on its way"
        description="Demographics, consent status, report history, a health-score gauge, and specialist suggestions will live here once Feature 2 lands."
      />
    </section>
  );
}
