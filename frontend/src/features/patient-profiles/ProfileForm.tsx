/**
 * Create/edit form for one patient profile.
 *
 * Only fields a supported workflow actually consumes are collected. Date of birth is the second
 * deterministic signal the document identity check uses, which is why it is requested up front
 * with that reason stated - not as an unexplained demographic field.
 */

import { useState } from 'react';
import type { FormEvent } from 'react';

import { Button } from '@/components/ui';

import styles from './patientProfiles.module.css';
import type { PatientProfile, PatientProfileInput } from './types';

const RELATIONSHIP_OPTIONS: Array<[string, string]> = [
  ['spouse', 'My spouse'],
  ['parent', 'My parent'],
  ['child', 'My child'],
  ['sibling', 'My sibling'],
  ['grandparent', 'My grandparent'],
  ['dependent', 'My dependent'],
  ['other', 'Someone else I care for'],
];

const DIETARY_OPTIONS: Array<[string, string]> = [
  ['', 'No preference'],
  ['vegetarian', 'Vegetarian'],
  ['vegan', 'Vegan'],
  ['eggetarian', 'Eggetarian'],
  ['pescatarian', 'Pescatarian'],
  ['halal', 'Halal'],
  ['jain', 'Jain'],
];

export interface ProfileFormValues extends PatientProfileInput {
  consentAccepted: boolean;
}

interface ProfileFormProps {
  initial?: PatientProfile | null;
  /** The owner's own profile cannot change its relationship, and needs no consent re-prompt. */
  mode: 'create' | 'edit';
  isSaving?: boolean;
  errorMessage?: string | null;
  submitLabel?: string;
  onSubmit: (values: ProfileFormValues) => void;
  onCancel?: () => void;
}

function toTokens(value: string): string[] {
  return value
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
}

export function ProfileForm({
  initial = null,
  mode,
  isSaving = false,
  errorMessage = null,
  submitLabel,
  onSubmit,
  onCancel,
}: ProfileFormProps) {
  const isOwner = initial?.isAccountOwnerProfile ?? false;

  const [displayName, setDisplayName] = useState(initial?.displayName ?? '');
  const [relationship, setRelationship] = useState<string>(
    initial?.relationshipToAccountOwner ?? 'child',
  );
  const [dateOfBirth, setDateOfBirth] = useState(initial?.dateOfBirth ?? '');
  const [sex, setSex] = useState(initial?.sex ?? '');
  const [city, setCity] = useState(initial?.city ?? '');
  const [dietaryPreference, setDietaryPreference] = useState(initial?.dietaryPreference ?? '');
  const [allergies, setAllergies] = useState((initial?.allergies ?? []).join(', '));
  const [intolerances, setIntolerances] = useState((initial?.foodIntolerances ?? []).join(', '));
  const [conditions, setConditions] = useState((initial?.knownConditions ?? []).join(', '));
  const [goals, setGoals] = useState((initial?.healthGoals ?? []).join(', '));
  const [consentAccepted, setConsentAccepted] = useState(mode === 'edit');
  const [localError, setLocalError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!displayName.trim()) {
      setLocalError('Enter the name of the person this profile is for.');
      return;
    }
    if (mode === 'create' && !consentAccepted) {
      setLocalError('Confirm consent before creating this profile.');
      return;
    }
    setLocalError(null);

    onSubmit({
      displayName: displayName.trim(),
      relationshipToAccountOwner: isOwner ? 'self' : relationship,
      dateOfBirth: dateOfBirth || null,
      sex: sex || null,
      city: city.trim() || null,
      dietaryPreference: dietaryPreference || null,
      allergies: toTokens(allergies),
      foodIntolerances: toTokens(intolerances),
      dislikedFoods: initial?.dislikedFoods ?? [],
      knownConditions: toTokens(conditions),
      healthGoals: toTokens(goals),
      consentAccepted,
    });
  }

  const message = errorMessage ?? localError;

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {message && (
        <p className={styles.formError} role="alert">
          {message}
        </p>
      )}

      <div className={styles.formRow}>
        <label className={styles.field}>
          <span>Full name</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="As it appears on their reports"
            autoComplete="off"
            required
          />
          <span className={styles.hint}>
            Matching this against the name printed on a document is how we keep records separate.
          </span>
        </label>

        {!isOwner && (
          <label className={styles.field}>
            <span>Relationship to you</span>
            <select
              value={relationship}
              onChange={(event) => setRelationship(event.target.value)}
            >
              {RELATIONSHIP_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className={styles.formRow}>
        <label className={styles.field}>
          <span>Date of birth (optional)</span>
          <input
            type="date"
            value={dateOfBirth}
            onChange={(event) => setDateOfBirth(event.target.value)}
          />
          <span className={styles.hint}>
            Used only to check that an uploaded document belongs to this person.
          </span>
        </label>

        <label className={styles.field}>
          <span>Sex (optional)</span>
          <select value={sex} onChange={(event) => setSex(event.target.value)}>
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
          <span className={styles.hint}>
            Some lab reference ranges differ by sex. Nothing else uses this.
          </span>
        </label>

        <label className={styles.field}>
          <span>City (optional)</span>
          <input value={city} onChange={(event) => setCity(event.target.value)} />
        </label>
      </div>

      <div className={styles.formRow}>
        <label className={styles.field}>
          <span>Allergies</span>
          <input
            value={allergies}
            onChange={(event) => setAllergies(event.target.value)}
            placeholder="peanut, shellfish"
          />
          <span className={styles.hint}>
            Comma separated. Always excluded from this person&apos;s meal plans.
          </span>
        </label>

        <label className={styles.field}>
          <span>Food intolerances</span>
          <input
            value={intolerances}
            onChange={(event) => setIntolerances(event.target.value)}
            placeholder="lactose"
          />
        </label>
      </div>

      <div className={styles.formRow}>
        <label className={styles.field}>
          <span>Dietary preference</span>
          <select
            value={dietaryPreference}
            onChange={(event) => setDietaryPreference(event.target.value)}
          >
            {DIETARY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span>Known conditions</span>
          <input
            value={conditions}
            onChange={(event) => setConditions(event.target.value)}
            placeholder="type 2 diabetes"
          />
        </label>

        <label className={styles.field}>
          <span>Health goals</span>
          <input
            value={goals}
            onChange={(event) => setGoals(event.target.value)}
            placeholder="balanced meals"
          />
        </label>
      </div>

      {mode === 'create' && (
        <div className={styles.consentBox}>
          <input
            id="profile-consent"
            type="checkbox"
            checked={consentAccepted}
            onChange={(event) => setConsentAccepted(event.target.checked)}
          />
          <label htmlFor="profile-consent">
            I confirm I am this person, or I am authorised to manage their health records, and I
            consent to their documents being processed to produce health information. This is not
            medical advice and does not replace a clinician.
          </label>
        </div>
      )}

      <div className={styles.formActions}>
        <Button type="submit" isLoading={isSaving}>
          {submitLabel ?? (mode === 'create' ? 'Create profile' : 'Save changes')}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isSaving}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
