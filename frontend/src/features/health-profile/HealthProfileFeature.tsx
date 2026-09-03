/**
 * Health Profile feature root - consent status, preferences form, report-history timeline,
 * health-score gauge, organ/system cards, and the specialist suggestion panel
 * (FR2.3, FR2.5-FR2.7; implementation-plan.md Section 5.4).
 */

import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { HealthScoreGauge } from '@/components/Charts';
import {
  Badge,
  Button,
  Card,
  Combobox,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from '@/components/ui';

import { ApiError, analyzeReport, fetchProfile, suggestSpecialists, updatePreferences } from './api';
import {
  ALLERGY_OPTIONS,
  BUDGET_OPTIONS,
  CUISINE_OPTIONS,
  GOAL_OPTIONS,
  LOCATION_OPTIONS,
} from './options';
import { ReportHistoryItem } from './ReportHistoryItem';
import styles from './health-profile.module.css';
import type { BadgeTone } from '@/components/ui';
import type { ReportAnalyzeResponse } from './types';

/** Mirrors the backend's structural token rule in `api/profile.py`, for UX only. */
const TOKEN_PATTERN = /^[a-z0-9][a-z0-9 -]{0,63}$/;

function normalizeToken(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

const tokenList = (label: string) =>
  z
    .array(z.string())
    .max(32, `Add at most 32 ${label}.`)
    .refine((tokens) => tokens.every((token) => TOKEN_PATTERN.test(normalizeToken(token))), {
      message: `Use letters, numbers and hyphens only (${label}).`,
    });

/** Single-select fields are modelled as a 0-or-1 entry array so one Combobox serves both modes. */
const singleValue = z.array(z.string().max(64, 'Keep this under 64 characters.')).max(1);

const preferencesSchema = z.object({
  allergies: tokenList('allergies'),
  goals: tokenList('goals'),
  cuisine: singleValue,
  budget: singleValue,
  location: singleValue,
});

type PreferencesForm = z.infer<typeof preferencesSchema>;

const RISK_TONES: Record<string, BadgeTone> = {
  typical: 'success',
  watch: 'warning',
  discuss: 'danger',
};

function riskTone(riskLevel: string): BadgeTone {
  return RISK_TONES[riskLevel] ?? 'neutral';
}

/** Confidence is a ranking signal from the backend, not a probability of any condition. */
function confidenceLabel(confidence: number): string {
  return `${Math.round(confidence * 100)}% match`;
}

export function HealthProfileFeature() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery({ queryKey: ['profile'], queryFn: fetchProfile });
  const profile = profileQuery.data?.data.profile;
  const reports = profileQuery.data?.data.reports ?? [];
  const latestSummary = profileQuery.data?.data.latestSummary ?? null;

  const [snapshot, setSnapshot] = useState<ReportAnalyzeResponse | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [openReportId, setOpenReportId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const specialistQuery = useQuery({
    queryKey: ['specialists', latestSummary?.reportId],
    queryFn: () => suggestSpecialists(latestSummary!.reportId),
    enabled: Boolean(latestSummary?.reportId),
  });

  const form = useForm<PreferencesForm>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: { allergies: [], goals: [], cuisine: [], budget: [], location: [] },
  });

  // Server state owns the form's initial values, so reset once the profile lands.
  useEffect(() => {
    if (profile) {
      form.reset({
        allergies: profile.preferences.allergies,
        goals: profile.preferences.goals,
        cuisine: profile.preferences.cuisine ? [profile.preferences.cuisine] : [],
        budget: profile.preferences.budget ? [profile.preferences.budget] : [],
        location: profile.preferences.location ? [profile.preferences.location] : [],
      });
    }
  }, [profile, form]);

  const saveMutation = useMutation({
    mutationFn: (values: PreferencesForm) =>
      updatePreferences({
        allergies: values.allergies.map(normalizeToken),
        goals: values.goals.map(normalizeToken),
        cuisine: values.cuisine[0]?.trim() || null,
        budget: values.budget[0]?.trim() || null,
        location: values.location[0]?.trim() || null,
        etag: profile?.etag ?? null,
      }),
    onSuccess: () => {
      setErrorMessage(null);
      setNoticeMessage('Preferences saved.');
      void queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
    onError: (error) => {
      setNoticeMessage(null);
      if (error instanceof ApiError && error.problem.status === 409) {
        setErrorMessage('This profile changed in another tab. Reloading the latest version - please re-apply your edits.');
        void queryClient.invalidateQueries({ queryKey: ['profile'] });
        return;
      }
      setErrorMessage(
        error instanceof ApiError ? error.problem.detail : 'Could not save your preferences right now.',
      );
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeReport(file!),
    onSuccess: (response) => {
      setErrorMessage(null);
      setSnapshot(response.data);
      setNoticeMessage(
        response.safety.notes.includes('report-date-not-detected')
          ? "No report date was printed on that file, so today's date was used instead."
          : null,
      );
      void queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
    onError: (error) => {
      setSnapshot(null);
      setErrorMessage(
        error instanceof ApiError ? error.problem.detail : 'Could not read that report. Please try another file.',
      );
    },
  });

  const guidance = specialistQuery.data?.data;
  const specialistSafety = specialistQuery.data?.safety;
  const gaugeScore = snapshot?.healthScore ?? latestSummary?.healthScore ?? null;
  const gaugeDate = snapshot?.reportDate ?? reports.find((r) => r.reportId === latestSummary?.reportId)?.reportDate;

  return (
    <section aria-label="Health Profile">
      <PageHeader
        eyebrow="AI-assisted"
        title="Health Profile & Specialist Advisor"
        description="Your consent status, preferences, report history, and which specialty category is worth discussing - always in non-diagnostic language."
        icon={<span aria-hidden="true">&#128100;</span>}
      />

      {profileQuery.isLoading && <LoadingState message="Loading your profile..." />}

      {profileQuery.isError && (
        <ErrorState message="Could not load your profile." onRetry={() => profileQuery.refetch()} />
      )}

      {errorMessage && (
        <ErrorState message={errorMessage} onRetry={() => setErrorMessage(null)} retryLabel="Dismiss" />
      )}

      {noticeMessage && (
        <ErrorState
          icon={<span aria-hidden="true">i</span>}
          message={noticeMessage}
          onRetry={() => setNoticeMessage(null)}
          retryLabel="Dismiss"
        />
      )}

      {profile && (
        <>
          <div className={styles.grid}>
            <Card title="Health indicator score" subtitle="A transparent rule-based score, not a diagnosis.">
              {gaugeScore === null ? (
                <p className={styles.meta}>Analyze a lab report to see your indicator score.</p>
              ) : (
                <HealthScoreGauge score={gaugeScore} reportDate={gaugeDate} />
              )}
            </Card>

            <Card title="Consent" subtitle="Recorded when you upload a report for analysis.">
              {profile.consent.version ? (
                <>
                  <div className={styles.chips}>
                    <Badge tone="success">Accepted v{profile.consent.version}</Badge>
                    {profile.consent.purposes.map((purpose) => (
                      <Badge key={purpose} tone="info">
                        {purpose}
                      </Badge>
                    ))}
                  </div>
                  <p className={styles.meta}>
                    Accepted on {new Date(profile.consent.acceptedAt!).toLocaleString()}.
                  </p>
                </>
              ) : (
                <p className={styles.meta}>
                  No consent recorded yet. It is captured the first time you analyze a report.
                </p>
              )}
            </Card>
          </div>

          <Card
            className={styles.card}
            title="Analyze a lab report"
            subtitle="PDF, JPG, PNG or HEIC, up to 10 MB. Adds the report to your history and refreshes the panels below."
          >
            <div className={styles.form}>
              <div className={styles.field}>
                <label className={styles.meta} htmlFor="profile-report-file">
                  Lab report file
                </label>
                <input
                  id="profile-report-file"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.heic"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </div>
              <Button onClick={() => analyzeMutation.mutate()} isLoading={analyzeMutation.isPending} disabled={!file}>
                Analyze report
              </Button>
            </div>
          </Card>

          {analyzeMutation.isPending && <LoadingState message="Reading and normalizing your report..." />}

          {snapshot && (
            <Card
              className={styles.card}
              title="Organ and system snapshot"
              subtitle={`From the report dated ${snapshot.reportDate}. Every value is compared against a typical reference range.`}
            >
              <div className={styles.grid}>
                {snapshot.systemCards.map((card) => (
                  <Card key={card.system} title={card.system} actions={<Badge tone={riskTone(card.riskLevel)}>{card.riskLevel}</Badge>}>
                    <p className={styles.meta}>{card.summary}</p>
                  </Card>
                ))}
              </div>
              <p className={styles.narrative}>{snapshot.narrative}</p>
            </Card>
          )}

          <Card
            className={styles.card}
            title="Report history"
            subtitle="Every report on record, newest first. Select one to see what drove its score."
          >
            {reports.length === 0 ? (
              <EmptyState
                icon={<span aria-hidden="true">&#128100;</span>}
                title="No reports yet"
                description="Analyze a lab report above and it will appear here as a timeline."
              />
            ) : (
              <ul className={styles.timeline}>
                {reports.map((report) => (
                  <ReportHistoryItem
                    key={report.reportId}
                    report={report}
                    isLatest={report.reportId === profile.latestSummaryId}
                    isOpen={openReportId === report.reportId}
                    onToggle={() =>
                      setOpenReportId((current) =>
                        current === report.reportId ? null : report.reportId,
                      )
                    }
                  />
                ))}
              </ul>
            )}
          </Card>

          <Card
            className={styles.card}
            title="Specialist suggestion"
            subtitle="A specialty category to discuss - never a named doctor, a diagnosis, or an urgency claim."
          >
            {specialistQuery.isLoading && <LoadingState message="Matching your results to specialty categories..." />}

            {specialistQuery.isError && (
              <ErrorState
                message="Could not load a specialist suggestion."
                onRetry={() => specialistQuery.refetch()}
              />
            )}

            {!latestSummary && !specialistQuery.isLoading && (
              <EmptyState
                icon={<span aria-hidden="true">&#128100;</span>}
                title="No report to work from yet"
                description="Analyze a lab report above to see which specialty category is worth discussing."
              />
            )}

            {guidance && specialistSafety?.pass === false && (
              <ErrorState message="This suggestion was withheld by the safety reviewer and cannot be shown." />
            )}

            {guidance && specialistSafety?.pass !== false && (
              <>
                <p className={styles.narrative}>{guidance.rationale}</p>

                {guidance.categories.map((category) => (
                  <div key={category.parameterGroup} className={styles.category}>
                    <div className={styles.categoryHead}>
                      <h3 className={styles.categoryName}>{category.specialtyCategory}</h3>
                      <Badge tone="info">{category.parameterGroup}</Badge>
                      <Badge tone="neutral">{confidenceLabel(category.confidence)}</Badge>
                    </div>
                    <p className={styles.meta}>{category.whenToConsult}</p>
                    <p className={styles.source}>
                      Source:{' '}
                      <a href={category.source.sourceUrl} target="_blank" rel="noreferrer noopener">
                        {category.source.sourceName}
                      </a>{' '}
                      ({category.source.sourceDate})
                    </p>
                  </div>
                ))}

                {guidance.doctorLinks.length > 0 && (
                  <ul className={styles.links}>
                    {guidance.doctorLinks.map((link) => (
                      <li key={link.url} className={styles.meta}>
                        <a href={link.url} target="_blank" rel="noreferrer noopener">
                          {link.name}
                        </a>{' '}
                        <Badge tone="neutral">{link.provenance}</Badge>
                      </li>
                    ))}
                  </ul>
                )}

                <p className={styles.source}>{guidance.disclaimer}</p>
              </>
            )}
          </Card>

          <Card
            className={styles.card}
            title="Preferences"
            subtitle="Used by the meal planner. Search the list, or type your own and pick 'Add'."
          >
            <form onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))} noValidate>
              <div className={styles.form}>
                <div className={styles.field}>
                  <Controller
                    control={form.control}
                    name="allergies"
                    render={({ field }) => (
                      <Combobox
                        label="Allergies"
                        options={ALLERGY_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        multiple
                        allowCustomValue
                        placeholder="Search allergies..."
                        error={form.formState.errors.allergies?.message}
                      />
                    )}
                  />
                </div>

                <div className={styles.field}>
                  <Controller
                    control={form.control}
                    name="goals"
                    render={({ field }) => (
                      <Combobox
                        label="Goals"
                        options={GOAL_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        multiple
                        allowCustomValue
                        placeholder="Search goals..."
                        error={form.formState.errors.goals?.message}
                      />
                    )}
                  />
                </div>

                <div className={styles.field}>
                  <Controller
                    control={form.control}
                    name="cuisine"
                    render={({ field }) => (
                      <Combobox
                        label="Cuisine"
                        options={CUISINE_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        allowCustomValue
                        placeholder="Search cuisines..."
                        error={form.formState.errors.cuisine?.message}
                      />
                    )}
                  />
                </div>

                <div className={styles.field}>
                  <Controller
                    control={form.control}
                    name="budget"
                    render={({ field }) => (
                      <Combobox
                        label="Budget"
                        options={BUDGET_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder="Select a budget..."
                        error={form.formState.errors.budget?.message}
                      />
                    )}
                  />
                </div>

                <div className={styles.field}>
                  <Controller
                    control={form.control}
                    name="location"
                    render={({ field }) => (
                      <Combobox
                        label="Location"
                        options={LOCATION_OPTIONS}
                        value={field.value}
                        onChange={field.onChange}
                        allowCustomValue
                        placeholder="Search locations..."
                        error={form.formState.errors.location?.message}
                      />
                    )}
                  />
                </div>
              </div>
              <div className={styles.actions}>
                <Button type="submit" isLoading={saveMutation.isPending}>
                  Save preferences
                </Button>
              </div>
            </form>
          </Card>
        </>
      )}
    </section>
  );
}
