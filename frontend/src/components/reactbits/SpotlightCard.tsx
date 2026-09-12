/**
 * React Bits "Spotlight Card" (https://reactbits.dev/components/spotlight-card) - a radial-gradient
 * glow that tracks the pointer over the card. Pure CSS/JS, no external dependency. Purely
 * decorative: pointer events are disabled on the glow layer so it never intercepts clicks/keyboard
 * activation on whatever interactive element wraps this.
 */

import { useRef } from 'react';
import type { MouseEvent, ReactNode } from 'react';

import styles from './SpotlightCard.module.css';

interface SpotlightCardProps {
  children: ReactNode;
  className?: string;
  spotlightColor?: string;
}

export function SpotlightCard({
  children,
  className = '',
  spotlightColor = 'rgba(255, 255, 255, 0.25)',
}: SpotlightCardProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    const root = rootRef.current;
    if (!root) {
      return;
    }
    const rect = root.getBoundingClientRect();
    root.style.setProperty('--spotlight-x', `${event.clientX - rect.left}px`);
    root.style.setProperty('--spotlight-y', `${event.clientY - rect.top}px`);
  };

  return (
    <div ref={rootRef} className={styles.card} style={{ '--spotlight-color': spotlightColor } as never} onMouseMove={handleMouseMove}>
      <div className={styles.glow} aria-hidden="true" />
      <div className={`${styles.content} ${className}`}>{children}</div>
    </div>
  );
}
