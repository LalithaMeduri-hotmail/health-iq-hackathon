import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';

import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/ui';
import { ApiError } from '@/lib/apiClient';

import { fetchMealPlanReports, generateMealPlan } from './api';
import styles from './meal-planner.module.css';
import type { MealPlan, MealPlanBudget, MealPlanMeal, MealPlanPreferences } from './types';

interface PlannerFormValues extends MealPlanPreferences {
  reportId: string;
}

const CUISINES = [
  { value: 'general', label: 'General' },
  { value: 'south-indian-veg', label: 'South Indian vegetarian' },
];

const BUDGETS: Array<{ value: MealPlanBudget; label: string }> = [
  { value: 'low', label: 'Budget friendly' },
  { value: 'medium', label: 'Moderate' },
  { value: 'high', label: 'Flexible' },
];

const MEAL_LABELS: Record<MealPlanMeal['type'], string> = {
  breakfast: 'Breakfast',
  lunch: 'Lunch',
  dinner: 'Dinner',
  snack: 'Snack',
};

function formatReportLabel(reportDate: string, labName: string): string {
  const date = new Intl.DateTimeFormat('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${reportDate}T00:00:00`));
  return `${date} - ${labName}`;
}

function SourceLink({ source }: { source: MealPlanMeal['source'] }) {
  return (
    <a className={styles.source} href={source.sourceUrl} target="_blank" rel="noreferrer">
      {source.sourceName} · {source.sourceDate}
    </a>
  );
}

function MealPlanResult({ plan }: { plan: MealPlan }) {
  return (
    <div className={styles.results} aria-live="polite">
      <div className={styles.resultHeading}>
        <div>
          <p className={styles.kicker}>Your meal plan</p>
          <h2>{plan.days.length}-day plan</h2>
        </div>
        <div className={styles.effectivePreferences} aria-label="Plan preferences">
          <span>{CUISINES.find((item) => item.value === plan.preferences.cuisine)?.label ?? plan.preferences.cuisine}</span>
          <span>{BUDGETS.find((item) => item.value === plan.preferences.budget)?.label ?? plan.preferences.budget}</span>
        </div>
      </div>

      {plan.conditionTags.length > 0 && (
        <div className={styles.signalStrip}>
          <span className={styles.signalLabel}>Report signals considered</span>
          <div className={styles.tags}>
            {plan.conditionTags.map((tag) => (
              <span className={styles.tag} key={tag}>{tag.split('-').join(' ')}</span>
            ))}
          </div>
        </div>
      )}

      <div className={styles.dayGrid}>
        {plan.days.map((day) => (
          <article className={styles.dayCard} key={day.day}>
            <header className={styles.dayHeader}>
              <span className={styles.dayNumber}>{String(day.day).padStart(2, '0')}</span>
              <h3>Day {day.day}</h3>
            </header>
            <div className={styles.meals}>
              {day.meals.map((meal) => (
                <section className={styles.meal} key={`${day.day}-${meal.type}`}>
                  <p className={styles.mealType}>{MEAL_LABELS[meal.type]}</p>
                  <ul className={styles.items}>
                    {meal.items.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                  <p className={styles.notes}>{meal.notes}</p>
                  <SourceLink source={meal.source} />
                </section>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className={styles.contextGrid}>
        <section className={styles.contextSection}>
          <p className={styles.kicker}>Why this plan</p>
          <h3>Grounded rationale</h3>
          <div className={styles.rationaleList}>
            {plan.rationale.map((item) => (
              <div className={styles.rationale} key={`${item.text}-${item.source.sourceUrl}`}>
                <p>{item.text}</p>
                <SourceLink source={item.source} />
              </div>
            ))}
          </div>
        </section>

        <section className={`${styles.contextSection} ${styles.avoidSection}`}>
          <p className={styles.kicker}>Keep off the plate</p>
          <h3>Avoid list</h3>
          <ul className={styles.avoidList}>
            {plan.avoidList.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>

      <p className={styles.planDisclaimer}>{plan.disclaimer}</p>
    </div>
  );
}

export function MealPlannerFeature() {
  const reportsQuery = useQuery({ queryKey: ['reports'], queryFn: fetchMealPlanReports });
  const reports = useMemo(() => reportsQuery.data?.data.reports ?? [], [reportsQuery.data]);
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { register, handleSubmit, setValue, watch } = useForm<PlannerFormValues>({
    defaultValues: { reportId: '', cuisine: 'general', budget: 'medium', days: 3 },
  });
  const reportId = watch('reportId');

  useEffect(() => {
    if (!reportId && reports.length > 0) {
      setValue('reportId', reports[0].reportId);
    }
  }, [reportId, reports, setValue]);

  const generateMutation = useMutation({
    mutationFn: generateMealPlan,
    onSuccess: (response) => {
      if (!response.safety.pass) {
        setPlan(null);
        setErrorMessage(response.safety.notes.join(' ') || 'Safety review suppressed this plan.');
        return;
      }
      setErrorMessage(null);
      setPlan(response.data);
    },
    onError: (error) => {
      setPlan(null);
      setErrorMessage(
        error instanceof ApiError
          ? error.problem.detail
          : 'The meal plan could not be generated. Please try again.',
      );
    },
  });

  const submit = handleSubmit(({ reportId: selectedReportId, cuisine, budget, days }) => {
    setErrorMessage(null);
    generateMutation.mutate({
      reportId: selectedReportId,
      preferences: { cuisine, budget, days: Number(days) },
    });
  });

  return (
    <section aria-label="Meal Planner">
      <PageHeader
        eyebrow="Condition-aware nutrition"
        title="AI Meal Planner"
        description="Build a practical meal plan from your selected health report and everyday preferences."
        icon={<span aria-hidden="true">&#127869;</span>}
      />

      <section className={styles.plannerPanel} aria-labelledby="planner-options-title">
        <div className={styles.panelIntro}>
          <p className={styles.kicker}>Plan setup</p>
          <h2 id="planner-options-title">Choose what works for you</h2>
          <p>Your saved allergies remain applied automatically.</p>
        </div>

        {reportsQuery.isLoading && <LoadingState message="Loading your health reports..." />}
        {reportsQuery.isError && (
          <ErrorState message="Could not load your health reports." onRetry={() => reportsQuery.refetch()} />
        )}
        {!reportsQuery.isLoading && !reportsQuery.isError && reports.length === 0 && (
          <EmptyState title="No health reports found" description="Add a health report before creating a meal plan." />
        )}

        {reports.length > 0 && (
          <form className={styles.form} onSubmit={submit}>
            <div className={`${styles.field} ${styles.reportField}`}>
              <label htmlFor="meal-plan-report">Health report</label>
              <select id="meal-plan-report" {...register('reportId', { required: true })}>
                {reports.map((report) => (
                  <option key={report.reportId} value={report.reportId}>
                    {formatReportLabel(report.reportDate, report.labName)}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label htmlFor="meal-plan-cuisine">Cuisine</label>
              <select id="meal-plan-cuisine" {...register('cuisine')}>
                {CUISINES.map((cuisine) => (
                  <option key={cuisine.value} value={cuisine.value}>{cuisine.label}</option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label htmlFor="meal-plan-budget">Budget</label>
              <select id="meal-plan-budget" {...register('budget')}>
                {BUDGETS.map((budget) => (
                  <option key={budget.value} value={budget.value}>{budget.label}</option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label htmlFor="meal-plan-days">Number of days</label>
              <select id="meal-plan-days" {...register('days', { valueAsNumber: true })}>
                {[1, 2, 3, 4, 5].map((days) => (
                  <option key={days} value={days}>{days} {days === 1 ? 'day' : 'days'}</option>
                ))}
              </select>
            </div>

            <Button type="submit" size="lg" isLoading={generateMutation.isPending} disabled={!reportId}>
              {generateMutation.isPending ? 'Building your plan' : 'Generate meal plan'}
            </Button>
          </form>
        )}
      </section>

      {errorMessage && (
        <div className={styles.feedback}>
          <ErrorState message={errorMessage} onRetry={() => void submit()} retryLabel="Generate again" />
        </div>
      )}

      {plan && <MealPlanResult plan={plan} />}
    </section>
  );
}
