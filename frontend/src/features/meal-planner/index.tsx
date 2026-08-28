/**
 * Meal Planner feature root (frontend.instructions.md colocation).
 *
 * TODO(D4): condition chips from latest report, allergy/cuisine/budget inputs -> 3-day plan
 * cards -> avoid list -> rationale with sources.
 */

import { EmptyState, PageHeader } from '@/components/ui';

export function MealPlannerFeature() {
  return (
    <section aria-label="Meal Planner">
      <PageHeader
        eyebrow="AI-assisted"
        title="AI Meal Planner"
        description="A doctor-reviewable, condition-aware meal plan built from your latest report and preferences."
        icon={<span aria-hidden="true">&#127869;</span>}
      />
      <EmptyState
        icon={<span aria-hidden="true">&#127869;</span>}
        title="Meal Planner is on its way"
        description="Tell us your allergies, cuisine, and goals and we'll build a doctor-reviewable 3-day plan with sourced rationale - coming with Feature 4."
      />
    </section>
  );
}
