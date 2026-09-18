/**
 * Patient assignment dialog for lab reports - opens when the name on the report is not the
 * active profile. A report is only re-analyzed once it is pointed at the right person's profile.
 */

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Button, Modal } from '@/components/ui';
import { useActiveProfile } from '@/features/patient-profiles';
import { createPatientProfile } from '@/features/patient-profiles/api';

import styles from './health-profile.module.css';

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

interface ReportPatientDialogProps {
  patientName: string;
  onContinue: (profileId: string) => void;
  onCancel: () => void;
}

export function ReportPatientDialog({ patientName, onContinue, onCancel }: ReportPatientDialogProps) {
  const queryClient = useQueryClient();
  const { activeProfile, profiles, setActiveProfile } = useActiveProfile();
  const [name, setName] = useState(patientName);
  const [relationship, setRelationship] = useState('child');
  const [error, setError] = useState<string | null>(null);

  const active = profiles.filter((profile) => profile.status === 'active');
  const existing = active.find(
    (profile) => normalizedName(profile.displayName) === normalizedName(patientName),
  );
  const others = active.filter((profile) => profile.id !== activeProfile?.id && profile.id !== existing?.id);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const showForm = !existing || isAddingNew;

  function continueWith(profileId: string) {
    setActiveProfile(profileId);
    onContinue(profileId);
  }

  const creation = useMutation({
    mutationFn: createPatientProfile,
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['patient-profiles'] });
      continueWith(response.data.id);
    },
    onError: () => setError('Could not create this profile. Try again.'),
  });

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
    <Modal isOpen title="Who is this report for?" onClose={onCancel}>
      <p className={styles.dialogRead}>
        Name on report: <strong>{patientName}</strong>
      </p>

      <p className={styles.dialogAlert} role="alert">
        This does not match {activeProfile?.displayName}.{' '}
        {existing ? 'A profile already exists for this patient.' : 'File it under a separate profile.'}
      </p>

      {existing && !isAddingNew && (
        <div className={styles.dialogActions}>
          <Button disabled={creation.isPending} onClick={() => continueWith(existing.id)}>
            Continue as {existing.displayName}
          </Button>
          <Button variant="secondary" disabled={creation.isPending} onClick={() => setIsAddingNew(true)}>
            Use another profile
          </Button>
        </div>
      )}

      {showForm && (
        <div className={styles.dialogForm}>
          {others.length > 0 && (
            <label className={styles.gateField}>
              <span>Existing profile</span>
              <select
                defaultValue=""
                disabled={creation.isPending}
                onChange={(event) => event.target.value && continueWith(event.target.value)}
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

          <div className={styles.gateFields}>
            <label className={styles.gateField}>
              <span>Full name</span>
              <input
                aria-label="Patient name"
                value={name}
                disabled={creation.isPending}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className={styles.gateField}>
              <span>Relationship</span>
              <select
                value={relationship}
                disabled={creation.isPending}
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
            <Button isLoading={creation.isPending} onClick={createAndContinue}>
              Add and continue
            </Button>
            {existing && (
              <Button variant="ghost" disabled={creation.isPending} onClick={() => setIsAddingNew(false)}>
                Back
              </Button>
            )}
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className={styles.dialogError}>
          {error}
        </p>
      )}

      <div className={styles.dialogFooter}>
        <Button variant="ghost" size="sm" disabled={creation.isPending} onClick={onCancel}>
          Cancel upload
        </Button>
      </div>
    </Modal>
  );
}
