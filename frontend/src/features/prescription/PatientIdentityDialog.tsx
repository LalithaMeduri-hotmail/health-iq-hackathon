/**
 * Patient assignment dialog - opens over the analyzer once a prescription is read.
 *
 * A name that does not match the account owner offers no "this is mine" path: the run has to be
 * filed under the right person's profile, so one patient's medicines never land in another's history.
 */

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Button, Modal } from '@/components/ui';
import { useActiveProfile } from '@/features/patient-profiles';
import { createPatientProfile } from '@/features/patient-profiles/api';

import { assignPrescription } from './api';
import styles from './prescription.module.css';

interface PatientIdentityDialogProps {
  runId: string;
  extractedName: string | null;
  onAssigned: () => void;
  onCancel: () => void;
}

const RELATIONSHIPS = [
  ['spouse', 'Spouse'],
  ['child', 'Child'],
  ['parent', 'Parent'],
  ['dependent', 'Dependent'],
  ['other', 'Other'],
] as const;

function normalizedName(value: string): string {
  return value.trim().toLocaleLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

export function PatientIdentityDialog({
  runId,
  extractedName,
  onAssigned,
  onCancel,
}: PatientIdentityDialogProps) {
  const queryClient = useQueryClient();
  const { profiles, setActiveProfile } = useActiveProfile();
  const owner = profiles.find((profile) => profile.isAccountOwnerProfile);
  const others = profiles.filter((profile) => !profile.isAccountOwnerProfile);
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState(extractedName ?? '');
  const [relationship, setRelationship] = useState('child');
  const [error, setError] = useState<string | null>(null);

  const isMismatch = Boolean(
    extractedName && owner && normalizedName(extractedName) !== normalizedName(owner.displayName),
  );
  const showForm = isMismatch || isCreating;

  const assignment = useMutation({
    mutationFn: (profileId: string) => assignPrescription(runId, profileId),
    onSuccess: (_response, profileId) => {
      setActiveProfile(profileId);
      onAssigned();
    },
    onError: () => setError('Could not assign this prescription. Try again.'),
  });

  const creation = useMutation({
    mutationFn: createPatientProfile,
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['patient-profiles'] });
      assignment.mutate(response.data.id);
    },
    onError: () => setError('Could not create this profile. Try again.'),
  });

  const isPending = assignment.isPending || creation.isPending;

  function createAndContinue() {
    if (!name.trim()) {
      setError('Enter the patient name.');
      return;
    }
    setError(null);
    creation.mutate({
      displayName: name.trim(),
      relationshipToAccountOwner: relationship,
      relationshipAssertion: 'I confirm I am authorized to manage this patient profile.',
      consentAccepted: true,
    });
  }

  return (
    <Modal isOpen title="Who is this prescription for?" onClose={onCancel}>
      {extractedName && (
        <p className={styles.dialogRead}>
          Name on prescription: <strong>{extractedName}</strong>
        </p>
      )}

      {isMismatch && (
        <p className={styles.dialogAlert} role="alert">
          This does not match {owner?.displayName}. File it under a separate profile.
        </p>
      )}

      {!showForm && (
        <div className={styles.dialogActions}>
          <Button disabled={!owner || isPending} onClick={() => owner && assignment.mutate(owner.id)}>
            {owner ? `It is for ${owner.displayName}` : 'Loading...'}
          </Button>
          <Button variant="secondary" disabled={isPending} onClick={() => setIsCreating(true)}>
            Someone else
          </Button>
        </div>
      )}

      {showForm && (
        <div className={styles.dialogForm}>
          {others.length > 0 && (
            <label className={styles.dialogField}>
              <span>Existing profile</span>
              <select
                defaultValue=""
                disabled={isPending}
                onChange={(event) => event.target.value && assignment.mutate(event.target.value)}
              >
                <option value="">Select a patient</option>
                {others.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.displayName}
                  </option>
                ))}
              </select>
            </label>
          )}

          {others.length > 0 && <div className={styles.dialogDivider}>or add a new patient</div>}

          <div className={styles.dialogRow}>
            <label className={styles.dialogField}>
              <span>Full name</span>
              <input
                aria-label="Patient name"
                value={name}
                disabled={isPending}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className={styles.dialogField}>
              <span>Relationship</span>
              <select
                value={relationship}
                disabled={isPending}
                onChange={(event) => setRelationship(event.target.value)}
              >
                {RELATIONSHIPS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <p className={styles.dialogFinePrint}>
            You confirm you are authorized to manage this person&apos;s health records.
          </p>

          <div className={styles.dialogActions}>
            <Button isLoading={isPending} onClick={createAndContinue}>
              Add and continue
            </Button>
            {!isMismatch && (
              <Button variant="ghost" disabled={isPending} onClick={() => setIsCreating(false)}>
                Back
              </Button>
            )}
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className={styles.identityError}>
          {error}
        </p>
      )}

      <div className={styles.dialogFooter}>
        <Button variant="ghost" size="sm" disabled={isPending} onClick={onCancel}>
          Cancel upload
        </Button>
      </div>
    </Modal>
  );
}
