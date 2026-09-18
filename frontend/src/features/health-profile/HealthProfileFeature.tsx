/**
 * Health Profile feature root - owns the server-state queries and mutations, and lays the page out
 * as a persistent score summary plus four tabbed sections (FR2.3, FR2.5-FR2.7).
 *
 * The active tab lives in the URL (`?tab=`) so a section can be linked to and survives a reload.
 */

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ErrorState, LoadingState, PageHeader } from '@/components/ui';
import { useActiveProfileOptional } from '@/features/patient-profiles';

import {
  ApiError,
  analyzeReport,
  fetchProfile,
  fetchReportDetail,
  suggestSpecialists,
  updatePreferences,
} from './api';
import { ConsentCard } from './ConsentCard';
import { LatestReportPanel } from './LatestReportPanel';
import { PreferencesCard } from './PreferencesCard';
import { ProfileSummary } from './ProfileSummary';
import { ProfileTabs } from './ProfileTabs';
import { ReportHistoryPanel } from './ReportHistoryPanel';
import { ReportPatientDialog } from './ReportPatientDialog';
import { ReportUploadCard } from './ReportUploadCard';
import styles from './health-profile.module.css';
import type { ProfileTab } from './ProfileTabs';
import type { Preferences } from './types';

const TAB_IDS = ['overview', 'reports', 'preferences'] as const;
type TabId = (typeof TAB_IDS)[number];

export function HealthProfileFeature() {
  const queryClient = useQueryClient();
  const activeProfile = useActiveProfileOptional();
  const activeProfileId = activeProfile?.activeProfileId ?? null;
  // Reading before the profile list resolves would fetch the account scope and then refetch,
  // briefly showing another patient's history.
  const isProfileResolved = !activeProfile || !activeProfile.isLoading;
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const activeTab: TabId = (TAB_IDS as readonly string[]).includes(requestedTab ?? '')
    ? (requestedTab as TabId)
    : 'overview';

  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [openReportId, setOpenReportId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [mismatchedReport, setMismatchedReport] = useState<{ file: File; patientName: string } | null>(null);

  const profileQuery = useQuery({
    queryKey: ['profile', activeProfileId],
    queryFn: () => fetchProfile(activeProfileId),
    enabled: isProfileResolved,
  });
  const profile = profileQuery.data?.data.profile;
  const reports = profileQuery.data?.data.reports ?? [];
  const latestSummary = profileQuery.data?.data.latestSummary ?? null;
  const latestReportId = latestSummary?.reportId ?? null;

  // Shares a cache key with the timeline rows, so opening the latest report costs no extra request.
  const latestDetailQuery = useQuery({
    queryKey: ['report-detail', activeProfileId, latestReportId],
    queryFn: () => fetchReportDetail(latestReportId!, activeProfileId),
    enabled: Boolean(latestReportId),
  });

  const specialistQuery = useQuery({
    queryKey: ['specialists', latestReportId],
    queryFn: () => suggestSpecialists(latestReportId!),
    enabled: Boolean(latestReportId),
  });

  const saveMutation = useMutation({
    mutationFn: (preferences: Preferences) => updatePreferences({ ...preferences, etag: profile?.etag ?? null }),
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
    mutationFn: ({ file, profileId }: { file: File; profileId?: string }) => analyzeReport(file, profileId),
    onSuccess: (response) => {
      setErrorMessage(null);
      setIsUploadOpen(false);
      const notes = response.safety.notes;
      const activeName = activeProfile?.activeProfile?.displayName;
      if (notes.includes('patient-identity-unverified')) {
        setNoticeMessage(
          `No patient name could be read from that file, so it was filed under ${activeName ?? 'this profile'} without an identity check.`,
        );
      } else if (notes.includes('report-date-not-detected')) {
        setNoticeMessage("No report date was printed on that file, so today's date was used instead.");
      } else {
        setNoticeMessage('Report analyzed. Your score and the panels below are up to date.');
      }
      void queryClient.invalidateQueries({ queryKey: ['profile'] });
      void queryClient.invalidateQueries({ queryKey: ['report-detail'] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.problem.type === 'https://healthiq/errors/profile-mismatch') {
        const patientName = error.problem.errors?.find((item) => item.field === 'patientName')?.issue;
        if (patientName && analyzeMutation.variables?.file) {
          setMismatchedReport({ file: analyzeMutation.variables.file, patientName });
          setErrorMessage(null);
          return;
        }
      }
      setErrorMessage(
        error instanceof ApiError ? error.problem.detail : 'Could not read that report. Please try another file.',
      );
    },
  });

  function selectTab(id: string) {
    setSearchParams(
      (params) => {
        const next = new URLSearchParams(params);
        next.set('tab', id);
        return next;
      },
      { replace: true },
    );
  }

  const tabs: ProfileTab[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'reports', label: 'Report history', count: reports.length },
    { id: 'preferences', label: 'Preferences' },
  ];

  return (
    <section aria-label="Health Profile">
      <PageHeader
        eyebrow="AI-assisted"
        title="Health Profile & Specialist Advisor"
        description="Your report history, what each result means, which specialty category is worth discussing, and the preferences that personalise it - always in non-diagnostic language."
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
        <p className={styles.notice} role="status">
          <span>{noticeMessage}</span>
          <button type="button" className={styles.noticeDismiss} onClick={() => setNoticeMessage(null)}>
            Dismiss
          </button>
        </p>
      )}

      {profile && (
        <>
          <ProfileSummary
            profile={profile}
            reports={reports}
            latestReportId={latestReportId}
            latestScore={latestSummary?.healthScore ?? null}
            latestDetail={latestDetailQuery.data?.data ?? null}
            showAnalyzeAction={!isUploadOpen && reports.length > 0}
            onAnalyzeClick={() => setIsUploadOpen(true)}
          />

          {(isUploadOpen || reports.length === 0) && (
            <ReportUploadCard
              isPending={analyzeMutation.isPending}
              onAnalyze={(file) => analyzeMutation.mutate({ file, profileId: activeProfileId ?? undefined })}
              onDismiss={reports.length > 0 ? () => setIsUploadOpen(false) : undefined}
            />
          )}

          {analyzeMutation.isPending && <LoadingState message="Reading and normalizing your report..." />}

          {mismatchedReport && (
            <ReportPatientDialog
              patientName={mismatchedReport.patientName}
              onContinue={(profileId) => {
                const file = mismatchedReport.file;
                setMismatchedReport(null);
                analyzeMutation.mutate({ file, profileId });
              }}
              onCancel={() => setMismatchedReport(null)}
            />
          )}

          <ConsentCard consent={profile.consent} />

          <ProfileTabs tabs={tabs} activeId={activeTab} onSelect={selectTab} />

          <div className={styles.panel} id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
            {activeTab === 'overview' && (
              <LatestReportPanel
                detail={latestDetailQuery.data?.data ?? null}
                guidance={
                  specialistQuery.data?.safety.pass === false ? null : (specialistQuery.data?.data ?? null)
                }
                isSuppressed={specialistQuery.data?.safety.pass === false}
                isLoading={Boolean(latestReportId) && latestDetailQuery.isLoading}
                isError={latestDetailQuery.isError}
                onRetry={() => latestDetailQuery.refetch()}
              />
            )}

            {activeTab === 'reports' && (
              <ReportHistoryPanel
                reports={reports}
                latestReportId={latestReportId}
                openReportId={openReportId}
                onToggleReport={(reportId) =>
                  setOpenReportId((current) => (current === reportId ? null : reportId))
                }
              />
            )}

            {activeTab === 'preferences' && (
              <PreferencesCard
                profile={profile}
                isSaving={saveMutation.isPending}
                onSave={(preferences) => saveMutation.mutate(preferences)}
              />
            )}
          </div>
        </>
      )}
    </section>
  );
}
