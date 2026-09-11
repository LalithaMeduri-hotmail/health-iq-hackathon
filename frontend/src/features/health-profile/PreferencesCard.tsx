/** Preferences tab: the meal-planner inputs plus the consent record they were captured under. */

import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button, Card, Combobox } from '@/components/ui';

import { ALLERGY_OPTIONS, BUDGET_OPTIONS, CUISINE_OPTIONS, GOAL_OPTIONS, LOCATION_OPTIONS } from './options';
import styles from './health-profile.module.css';
import type { Preferences, Profile } from './types';

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

interface PreferencesCardProps {
  profile: Profile;
  isSaving: boolean;
  onSave: (preferences: Preferences) => void;
}

export function PreferencesCard({ profile, isSaving, onSave }: PreferencesCardProps) {
  const form = useForm<PreferencesForm>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: { allergies: [], goals: [], cuisine: [], budget: [], location: [] },
  });
  const { reset } = form;

  // Server state owns the form's initial values, so reset once the profile lands.
  useEffect(() => {
    reset({
      allergies: profile.preferences.allergies,
      goals: profile.preferences.goals,
      cuisine: profile.preferences.cuisine ? [profile.preferences.cuisine] : [],
      budget: profile.preferences.budget ? [profile.preferences.budget] : [],
      location: profile.preferences.location ? [profile.preferences.location] : [],
    });
  }, [profile, reset]);

  const submit = form.handleSubmit((values) =>
    onSave({
      allergies: values.allergies.map(normalizeToken),
      goals: values.goals.map(normalizeToken),
      cuisine: values.cuisine[0]?.trim() || null,
      budget: values.budget[0]?.trim() || null,
      location: values.location[0]?.trim() || null,
    }),
  );

  return (
    <Card
      title="Preferences"
      subtitle="Used by the meal planner and for local context. Search the list, or type your own and pick 'Add'."
    >
        <form onSubmit={submit} noValidate>
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
            <Button type="submit" isLoading={isSaving}>
              Save preferences
            </Button>
          </div>
        </form>
    </Card>
  );
}
