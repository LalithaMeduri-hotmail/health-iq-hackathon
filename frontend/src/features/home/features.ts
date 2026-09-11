/** Static catalogue of the four HealthIQ capabilities, ordered to match the primary navigation. */

export interface HomeFeatureCard {
  id: string;
  to: string;
  title: string;
  summary: string;
  /** Small emoji logo rendered in the badge that overlaps the animated banner (decorative). */
  glyph: string;
  /** Accent used for the card art/glow so each capability is visually distinct. */
  accent: 'brand' | 'teal' | 'indigo' | 'amber';
  highlights: string[];
  cta: string;
}

export const HOME_FEATURES: HomeFeatureCard[] = [
  {
    id: 'profile',
    to: '/profile',
    title: 'Health Report',
    summary: 'Understand your lab results in plain language, and which specialist is worth consulting.',
    glyph: '\u{1FA7A}',
    accent: 'teal',
    highlights: [
      'Out-of-range parameters mapped to body systems',
      'Suggested specialist types with reasoning',
      'Reference ranges shown alongside every value',
      'Safe, non-diagnostic language throughout',
    ],
    cta: 'See my health report',
  },
  {
    id: 'prescriptions',
    to: '/prescriptions',
    title: 'Prescription Check',
    summary: 'Check a prescription for lower-cost equivalents of the medicines you were given.',
    glyph: '\u{1F48A}',
    accent: 'brand',
    highlights: [
      'OCR with visible confidence scores',
      'Confirm low-confidence medicine names before analysis',
      'Estimated savings with source and date',
      'Alternatives always marked doctor-approval-required',
    ],
    cta: 'Check my medicines',
  },
  {
    id: 'comparison',
    to: '/comparison',
    title: 'Report Trends',
    summary: 'See what changed between two reports, so you know whether things are moving the right way.',
    glyph: '\u{1F4C8}',
    accent: 'indigo',
    highlights: [
      'Before/after tables with colour-coded deltas',
      'Trend lines for repeated parameters',
      'Improved, worsened, and stable groupings',
      'Units and provenance labelled on every metric',
    ],
    cta: 'See my trends',
  },
  {
    id: 'meal-plan',
    to: '/meal-plan',
    title: 'Meal Plan',
    summary: 'Get food guidance built around your latest results, allergies, and budget.',
    glyph: '\u{1F957}',
    accent: 'amber',
    highlights: [
      'Condition chips pulled from your latest report',
      'Allergy, cuisine, and budget preferences',
      'Three-day plan with an explicit avoid list',
      'Rationale grounded in cited nutrition sources',
    ],
    cta: 'Plan my meals',
  },
];
