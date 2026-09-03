/**
 * Curated pick-lists for the preferences form.
 *
 * These are UX suggestions only. The backend validates preference tokens structurally, not
 * against an allowlist (`api/profile.py`), and the meal planner treats the stored profile as the
 * authoritative allergen list (docs/lld/5-low-level-design-ai-meal-planner.md assumption A4) -
 * so every list below stays open to custom entries.
 *
 * Tokens must satisfy the backend rule `^[a-z0-9][a-z0-9 -]{0,63}$` and must not contain commas.
 */

/** The major food allergens most commonly declared on labels. */
export const ALLERGY_OPTIONS = [
  'peanut',
  'tree nut',
  'shellfish',
  'fish',
  'egg',
  'milk',
  'soy',
  'wheat',
  'gluten',
  'sesame',
  'mustard',
  'lactose',
];

/** Goals phrased against the canonical parameters in `data/reference_ranges`. */
export const GOAL_OPTIONS = [
  'reduce-hba1c',
  'reduce-fasting-glucose',
  'lower-ldl',
  'raise-hdl',
  'lower-triglycerides',
  'improve-vitamin-d',
  'improve-vitamin-b12',
  'raise-hemoglobin',
  'support-thyroid',
  'support-kidney-health',
  'support-liver-health',
  'manage-weight',
];

export const CUISINE_OPTIONS = [
  'south-indian-veg',
  'south-indian-nonveg',
  'north-indian-veg',
  'north-indian-nonveg',
  'bengali',
  'gujarati',
  'maharashtrian',
  'mediterranean',
  'continental',
  'east-asian',
];

export const BUDGET_OPTIONS = ['low', 'medium', 'high'];

export const LOCATION_OPTIONS = [
  'Ahmedabad',
  'Bengaluru',
  'Chennai',
  'Delhi',
  'Hyderabad',
  'Jaipur',
  'Kochi',
  'Kolkata',
  'Lucknow',
  'Mumbai',
  'Pune',
];
