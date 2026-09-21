/**
 * Patient profile management: list, create, edit, archive, switch.
 *
 * Doubles as first-run onboarding - when the account has no profile yet, the page shows the
 * create form on its own rather than an empty list, so the first thing a new user does is name
 * the person whose records they are about to upload.
 */

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
} from '@/components/ui';
import { ApiError } from '@/lib/apiClient';

import { useActiveProfile } from './ActiveProfileContext';
import {
  archivePatientProfile,
  createPatientProfile,
  grantConsent,
  restorePatientProfile,
  updatePatientProfile,
  withdrawConsent,
} from './api';
import { ProfileForm } from './ProfileForm';
import type { ProfileFormValues } from './ProfileForm';
import { PrescriptionHistory } from './PrescriptionHistory';
import { initials, relationshipLabel } from './ProfileSelector';
import styles from './patientProfiles.module.css';
import type { PatientProfile } from './types';

function problemMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.problem.detail || error.problem.title;
  }
  return 'Something went wrong. Please try again.';
}

function ProfileCard({
  profile,
  isActive,
  onEdit,
  onArchive,
  onRestore,
  onSwitch,
  onConsent,
  isBusy,
}: {
  profile: PatientProfile;
  isActive: boolean;
  onEdit: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onSwitch: () => void;
  onConsent: (grant: boolean) => void;
  isBusy: boolean;
}) {
  const isArchived = profile.status === 'archived';

  return (
    <Card className={isArchived ? styles.archived : undefined}>
      <div className={styles.profileCardHeader}>
        <div className={styles.profileCardTitle}>
          <span className={styles.profileCardName}>{profile.displayName}</span>
          <span className={styles.profileCardMeta}>{relationshipLabel(profile)}</span>
        </div>
        <span className={styles.selectorAvatar} aria-hidden="true">
          {initials(profile.displayName)}
        </span>
      </div>

      <div className={styles.badgeRow}>
        {isActive && <Badge tone="success">Active profile</Badge>}
        {isArchived && <Badge tone="neutral">Archived &middot; read only</Badge>}
        {profile.consentStatus === 'granted' ? (
          <Badge tone="info">Consent on file</Badge>
        ) : (
          <Badge tone="warning">Consent {profile.consentStatus}</Badge>
        )}
        {profile.allergies.length > 0 && (
          <Badge tone="warning">{profile.allergies.length} allergy exclusion(s)</Badge>
        )}
      </div>

      <div className={styles.cardActions}>
        {!isArchived && !isActive && (
          <Button size="sm" onClick={onSwitch} disabled={isBusy}>
            Switch to this profile
          </Button>
        )}
        {!isArchived && (
          <Button size="sm" variant="secondary" onClick={onEdit} disabled={isBusy}>
            Edit
          </Button>
        )}
        {!isArchived && profile.consentStatus === 'granted' && (
          <Button size="sm" variant="ghost" onClick={() => onConsent(false)} disabled={isBusy}>
            Withdraw consent
          </Button>
        )}
        {!isArchived && profile.consentStatus !== 'granted' && (
          <Button size="sm" variant="ghost" onClick={() => onConsent(true)} disabled={isBusy}>
            Grant consent
          </Button>
        )}
        {!isArchived && !profile.isAccountOwnerProfile && (
          <Button size="sm" variant="danger" onClick={onArchive} disabled={isBusy}>
            Archive
          </Button>
        )}
        {isArchived && (
          <Button size="sm" variant="secondary" onClick={onRestore} disabled={isBusy}>
            Restore
          </Button>
        )}
      </div>
    </Card>
  );
}

export function PatientProfilesFeature() {
  const queryClient = useQueryClient();
  const { profiles, activeProfileId, isLoading, error, setActiveProfile, needsOnboarding } =
    useActiveProfile();

  const [editing, setEditing] = useState<PatientProfile | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [pendingArchive, setPendingArchive] = useState<PatientProfile | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['patient-profiles'] });

  const creation = useMutation({
    mutationFn: createPatientProfile,
    onSuccess: async (response) => {
      await invalidate();
      setIsCreating(false);
      setFormError(null);
      setActiveProfile(response.data.id);
    },
    onError: (mutationError) => setFormError(problemMessage(mutationError)),
  });

  const update = useMutation({
    mutationFn: ({ profileId, values }: { profileId: string; values: ProfileFormValues }) =>
      updatePatientProfile(profileId, values),
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      setFormError(null);
    },
    onError: (mutationError) => setFormError(problemMessage(mutationError)),
  });

  const archive = useMutation({
    mutationFn: archivePatientProfile,
    onSuccess: async () => {
      await invalidate();
      setPendingArchive(null);
    },
  });

  const restore = useMutation({ mutationFn: restorePatientProfile, onSuccess: invalidate });
  const consent = useMutation({
    mutationFn: ({ profileId, grant }: { profileId: string; grant: boolean }) =>
      grant ? grantConsent(profileId) : withdrawConsent(profileId),
    onSuccess: invalidate,
  });

  const isBusy =
    creation.isPending ||
    update.isPending ||
    archive.isPending ||
    restore.isPending ||
    consent.isPending;

  const activeProfile = profiles.find((profile) => profile.id === activeProfileId) ?? null;

  if (isLoading) {
    return <LoadingState message="Loading patient profiles..." />;
  }

  if (error) {
    return <ErrorState message={problemMessage(error)} onRetry={() => void invalidate()} />;
  }

  if (needsOnboarding || (isCreating && profiles.length === 0)) {
    return (
      <>
        <PageHeader
          eyebrow="Getting started"
          title="Who are these health records for?"
          description="Create a profile for yourself, or for a family member you look after. Every document, analysis, and meal plan belongs to exactly one profile."
        />
        <Card>
          <ProfileForm
            mode="create"
            isSaving={creation.isPending}
            errorMessage={formError}
            submitLabel="Create profile and continue"
            onSubmit={(values) => creation.mutate({ ...values, consentAccepted: true })}
          />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Patients"
        title="Patient profiles"
        description="Each profile keeps its own documents, analyses, comparisons, and meal plans. Nothing is shared between them."
        actions={
          <Button onClick={() => {
            setFormError(null);
            setIsCreating(true);
          }}>
            Add a profile
          </Button>
        }
      />

      {profiles.length === 0 ? (
        <EmptyState
          title="No profiles yet"
          description="Add the first person whose health records you want to manage."
        />
      ) : (
        <div className={styles.list}>
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              isActive={profile.id === activeProfileId}
              isBusy={isBusy}
              onEdit={() => {
                setFormError(null);
                setEditing(profile);
              }}
              onArchive={() => setPendingArchive(profile)}
              onRestore={() => restore.mutate(profile.id)}
              onSwitch={() => setActiveProfile(profile.id)}
              onConsent={(grant) => consent.mutate({ profileId: profile.id, grant })}
            />
          ))}
        </div>
      )}

      {activeProfile && (
        <section className={styles.rxSection} aria-labelledby="issued-prescriptions">
          <p className={styles.rxSectionEyebrow}>History</p>
          <h2 className={styles.rxSectionTitle} id="issued-prescriptions">
            Health IQ prescriptions
          </h2>
          <p className={styles.rxSectionDesc}>
            Prescriptions issued for {activeProfile.displayName} after a doctor reviewed them. Each
            one is kept exactly as approved, including the prices at the time.
          </p>
          <PrescriptionHistory
            profileId={activeProfile.id}
            profileName={activeProfile.displayName}
          />
        </section>
      )}

      {isCreating && (
        <Modal isOpen title="Add a patient profile" onClose={() => setIsCreating(false)}>
          <ProfileForm
            mode="create"
            isSaving={creation.isPending}
            errorMessage={formError}
            onSubmit={(values) => creation.mutate({ ...values, consentAccepted: true })}
            onCancel={() => setIsCreating(false)}
          />
        </Modal>
      )}

      {editing && (
        <Modal isOpen title={`Edit ${editing.displayName}`} onClose={() => setEditing(null)}>
          <ProfileForm
            mode="edit"
            initial={editing}
            isSaving={update.isPending}
            errorMessage={formError}
            onSubmit={(values) => update.mutate({ profileId: editing.id, values })}
            onCancel={() => setEditing(null)}
          />
        </Modal>
      )}

      {pendingArchive && (
        <Modal
          isOpen
          title={`Archive ${pendingArchive.displayName}?`}
          onClose={() => setPendingArchive(null)}
        >
          <p>
            Archiving keeps every existing document and result readable, but this profile will not
            accept new uploads or new analysis. Medical records are never deleted automatically.
          </p>
          <div className={styles.formActions}>
            <Button
              variant="danger"
              isLoading={archive.isPending}
              onClick={() => archive.mutate(pendingArchive.id)}
            >
              Archive profile
            </Button>
            <Button variant="ghost" onClick={() => setPendingArchive(null)}>
              Keep it active
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
