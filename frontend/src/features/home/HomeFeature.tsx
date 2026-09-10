/**
 * Home dashboard: personalised greeting plus the four capability cards.
 *
 * Each card is a single navigating surface (click / Enter / Space opens the real route). A nested
 * "details" toggle expands the highlights inline without leaving the dashboard, so the card can
 * either expand or open depending on what the user clicks.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

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

      <div className={styles.body}>
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
      </div>
    </article>
  );
}

export function HomeFeature() {
  const { account } = useAuth();
  const name = account?.displayName ?? account?.username ?? null;

  return (
    <section className={styles.page} aria-label="HealthIQ home">
      <div className={styles.hero}>
        <p className={styles.heroEyebrow}>Your health workspace</p>
        <h1 className={styles.heroTitle}>
          {greeting(new Date())}
          {name ? `, ${name}` : ''}
        </h1>
        <p className={styles.heroSubtitle}>
          Pick a capability to get started. Everything here is informational and meant to help you have a better
          conversation with your doctor - it is never a diagnosis.
        </p>
      </div>

      <div className={styles.grid}>
        {HOME_FEATURES.map((feature) => (
          <FeatureTile key={feature.id} feature={feature} />
        ))}
      </div>
    </section>
  );
}
