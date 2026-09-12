/**
 * Home dashboard: personalised greeting plus the four capability cards.
 *
 * Each card is a single navigating surface (click / Enter / Space opens the real route). A nested
 * "details" toggle expands the highlights inline without leaving the dashboard, so the card can
 * either expand or open depending on what the user clicks.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import logoDarkUrl from '@/assets/logo-icon-dark.png';
import { LiquidEther, ShinyText, SpotlightCard, SplitText } from '@/components/reactbits';
import { useTheme } from '@/components/ThemeProvider';
import { useAuth } from '@/features/auth';

import { FeatureArt } from './FeatureArt';
import { HOME_FEATURES } from './features';
import type { HomeFeatureCard } from './features';
import styles from './home.module.css';

function greeting(now: Date): string {
  const hour = now.getHours();
  if (hour < 12) {
    return 'Good morning';
  }
  if (hour < 17) {
    return 'Good afternoon';
  }
  return 'Good evening';
}

interface FeatureTileProps {
  feature: HomeFeatureCard;
}

function FeatureTile({ feature }: FeatureTileProps) {
  const navigate = useNavigate();
  const [isExpanded, setIsExpanded] = useState(false);
  const detailsId = `feature-details-${feature.id}`;

  const open = () => navigate(feature.to);

  return (
    <article
      className={`${styles.tile} ${styles[feature.accent]} ${isExpanded ? styles.tileExpanded : ''}`}
      role="link"
      tabIndex={0}
      aria-label={`${feature.title}. ${feature.summary}`}
      onClick={open}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open();
        }
      }}
    >
      <div className={styles.media} aria-hidden="true">
        <FeatureArt id={feature.id} />
        <span className={styles.tileBadge}>{feature.glyph}</span>
      </div>

      <SpotlightCard className={styles.body} spotlightColor="var(--tile-accent-spotlight, rgba(255, 255, 255, 0.3))">
        <h2 className={styles.tileTitle}>{feature.title}</h2>
        <p className={styles.tileSummary}>{feature.summary}</p>

        <div id={detailsId} className={styles.tileDetails} hidden={!isExpanded}>
          <ul className={styles.highlights}>
            {feature.highlights.map((highlight) => (
              <li key={highlight}>{highlight}</li>
            ))}
          </ul>
        </div>

        <footer className={styles.tileFooter}>
          <button
            type="button"
            className={styles.detailsButton}
            aria-expanded={isExpanded}
            aria-controls={detailsId}
            onClick={(event) => {
              event.stopPropagation();
              setIsExpanded((expanded) => !expanded);
            }}
          >
            {isExpanded ? 'Hide details' : 'What you get'}
            <span className={`${styles.chevron} ${isExpanded ? styles.chevronOpen : ''}`} aria-hidden="true" />
          </button>

          <span className={styles.tileCta}>
            {feature.cta}
            <span className={styles.arrow} aria-hidden="true">
              &#8594;
            </span>
          </span>
        </footer>
      </SpotlightCard>
    </article>
  );
}

/** Animated brand lockup that fills the empty space beside the hero copy, with the four
 * capability titles crossfading through it so the panel doubles as a feature teaser. */
function BrandPanel({ logoSrc }: { logoSrc: string }) {
  return (
    <div className={styles.heroBrand} aria-hidden="true">
      <img src={logoSrc} alt="" className={styles.heroBrandLogo} />
      <p className={styles.heroBrandWordmark}>
        Health<span className={styles.heroBrandAccent}>IQ</span>
      </p>
      <div className={styles.heroBrandFeatures}>
        {HOME_FEATURES.map((feature, index) => (
          <span
            key={feature.id}
            className={styles.heroBrandFeature}
            style={{ animationDelay: `${index * -2}s` }}
          >
            <span aria-hidden="true">{feature.glyph}</span> {feature.title}
          </span>
        ))}
      </div>
    </div>
  );
}

export function HomeFeature() {
  const { account } = useAuth();
  const { theme } = useTheme();
  const name = account?.displayName ?? account?.username ?? null;
  const isLight = theme === 'light';

  return (
    <section className={styles.page} aria-label="HealthIQ home">
      <LiquidEther
        className={styles.pageBg}
        lightMode={isLight}
        colors={['#22c55e', '#14b8a6', '#4f46e5']}
        backgroundColor={isLight ? '#f0fdf4' : '#0a0f1a'}
        autoDemo
        autoSpeed={0.5}
        mouseForce={18}
        resolution={0.5}
      />

      <div className={styles.hero}>
        <BrandPanel logoSrc={isLight ? logoUrl : logoDarkUrl} />

        <div className={styles.heroContent}>
          <SplitText
            key={name ?? 'guest'}
            tag="p"
            text={`${greeting(new Date())}${name ? `, ${name}` : ''}`}
            className={styles.heroGreeting}
            splitType="words"
          />
          <h1 className={styles.heroEyebrow}>
            <ShinyText text="Your AI-powered health companion" />
          </h1>
          <p className={styles.heroSubtitle}>
            From lab results to prescriptions, HealthIQ decodes your health data in plain English, flags cheaper
            medicine swaps, and tracks your progress over time - so you walk into your next appointment with
            answers, not just questions.
          </p>
        </div>
      </div>

      <div className={styles.grid}>
        {HOME_FEATURES.map((feature) => (
          <FeatureTile key={feature.id} feature={feature} />
        ))}
      </div>
    </section>
  );
}
