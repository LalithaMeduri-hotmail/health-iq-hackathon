/**
 * Looping animated artwork for each home card - vector "motion banners" instead of GIF/video files
 * so nothing binary ships, playback is crisp at any size, and `prefers-reduced-motion` can pause it.
 */

import styles from './home.module.css';

function PrescriptionArt() {
  return (
    <svg className={styles.art} viewBox="0 0 320 140" role="presentation" focusable="false">
      <g className={styles.artFloat}>
        <rect x="104" y="20" width="112" height="100" rx="10" fill="rgba(255,255,255,0.92)" />
        <rect x="118" y="36" width="52" height="7" rx="3.5" fill="currentColor" opacity="0.35" />
        <rect x="118" y="52" width="84" height="6" rx="3" fill="currentColor" opacity="0.18" />
        <rect x="118" y="66" width="70" height="6" rx="3" fill="currentColor" opacity="0.18" />
        <rect x="118" y="80" width="80" height="6" rx="3" fill="currentColor" opacity="0.18" />
        <rect x="118" y="94" width="46" height="6" rx="3" fill="currentColor" opacity="0.18" />
      </g>

      <g transform="translate(266 76) rotate(-24)">
        <g className={styles.artCapsule}>
          <rect x="-30" y="-13" width="60" height="26" rx="13" fill="rgba(255,255,255,0.95)" />
          <path d="M-30 0a13 13 0 0 1 13-13H0v26h-17A13 13 0 0 1-30 0z" fill="currentColor" opacity="0.8" />
        </g>
      </g>

      <g transform="translate(62 74)">
        <g className={styles.artPulseDot}>
          <circle r="20" fill="currentColor" opacity="0.16" />
          <circle r="10" fill="currentColor" opacity="0.5" />
        </g>
      </g>

      <rect className={styles.artScan} x="96" y="14" width="128" height="4" rx="2" fill="currentColor" />
    </svg>
  );
}

function HealthProfileArt() {
  return (
    <svg className={styles.art} viewBox="0 0 320 140" role="presentation" focusable="false">
      <path
        d="M0 78h64l12-40 16 68 14-52 11 24h30l10-16 12 16h151"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.18"
      />
      <path
        className={styles.artTrace}
        d="M0 78h64l12-40 16 68 14-52 11 24h30l10-16 12 16h151"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <g transform="translate(272 34)">
        <g className={styles.artHeartbeat}>
          <path
            d="M0 30c-16-11-26-19-26-30a13 13 0 0 1 26-6 13 13 0 0 1 26 6c0 11-10 19-26 30z"
            fill="rgba(255,255,255,0.95)"
          />
          <path
            d="M0 30c-16-11-26-19-26-30a13 13 0 0 1 26-6 13 13 0 0 1 26 6c0 11-10 19-26 30z"
            fill="currentColor"
            opacity="0.28"
          />
        </g>
      </g>
    </svg>
  );
}

function ComparisonArt() {
  const bars = [
    { x: 40, height: 40, delay: '0s' },
    { x: 84, height: 64, delay: '0.15s' },
    { x: 128, height: 52, delay: '0.3s' },
    { x: 172, height: 82, delay: '0.45s' },
    { x: 216, height: 68, delay: '0.6s' },
    { x: 260, height: 96, delay: '0.75s' },
  ];

  return (
    <svg className={styles.art} viewBox="0 0 320 140" role="presentation" focusable="false">
      {bars.map((bar) => (
        <rect
          key={bar.x}
          className={styles.artBar}
          style={{ animationDelay: bar.delay }}
          x={bar.x}
          y={120 - bar.height}
          width="24"
          height={bar.height}
          rx="6"
          fill="rgba(255,255,255,0.9)"
        />
      ))}
      <polyline
        className={styles.artTrace}
        points="52,84 96,60 140,72 184,40 228,54 272,26"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle className={styles.artPulseDot} cx="272" cy="26" r="7" fill="currentColor" />
    </svg>
  );
}

function MealPlanArt() {
  return (
    <svg className={styles.art} viewBox="0 0 320 140" role="presentation" focusable="false">
      <circle cx="160" cy="72" r="52" fill="rgba(255,255,255,0.92)" />
      <circle cx="160" cy="72" r="40" fill="currentColor" opacity="0.12" />
      <g className={styles.artSpin} style={{ transformOrigin: '160px 72px' }}>
        <circle cx="160" cy="44" r="13" fill="currentColor" opacity="0.75" />
        <circle cx="184" cy="86" r="13" fill="currentColor" opacity="0.5" />
        <circle cx="136" cy="86" r="13" fill="currentColor" opacity="0.32" />
      </g>
      <g className={styles.artFloat}>
        <path d="M52 92c0-24 18-42 42-42 0 24-18 42-42 42z" fill="currentColor" opacity="0.55" />
        <path d="M52 92c8-14 20-24 34-30" stroke="rgba(255,255,255,0.85)" strokeWidth="3" fill="none" strokeLinecap="round" />
      </g>
      <g className={styles.artFloatSlow}>
        <path d="M268 58c0 20-15 36-35 36 0-20 15-36 35-36z" fill="currentColor" opacity="0.4" />
      </g>
    </svg>
  );
}

const ART_BY_ID: Record<string, () => JSX.Element> = {
  prescriptions: PrescriptionArt,
  profile: HealthProfileArt,
  comparison: ComparisonArt,
  'meal-plan': MealPlanArt,
};

export function FeatureArt({ id }: { id: string }) {
  const Art = ART_BY_ID[id];
  return Art ? <Art /> : null;
}
