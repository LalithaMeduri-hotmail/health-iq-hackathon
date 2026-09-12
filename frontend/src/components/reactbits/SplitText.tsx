/**
 * React Bits "Split Text" (https://reactbits.dev/text-animations/split-text), adapted to this
 * project's CSS-module conventions. Splits `text` into per-character/word spans and reveals them
 * with a GSAP stagger once the element scrolls into view (native `IntersectionObserver`, no GSAP
 * ScrollTrigger plugin needed).
 */

import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

import styles from './SplitText.module.css';

interface SplitTextProps {
  text: string;
  tag?: 'h1' | 'h2' | 'h3' | 'p' | 'span';
  className?: string;
  delay?: number;
  duration?: number;
  splitType?: 'chars' | 'words';
  threshold?: number;
}

export function SplitText({
  text,
  tag: Tag = 'p',
  className = '',
  delay = 30,
  duration = 0.6,
  splitType = 'chars',
  threshold = 0.1,
}: SplitTextProps) {
  const containerRef = useRef<HTMLElement | null>(null);
  const units = splitType === 'words' ? text.split(/(\s+)/) : Array.from(text);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const targets = container.querySelectorAll(`.${styles.unit}`);

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      gsap.set(targets, { opacity: 1, y: 0 });
      return;
    }

    gsap.set(targets, { opacity: 0, y: 18 });

    const animate = () => {
      gsap.to(targets, { opacity: 1, y: 0, duration, ease: 'power3.out', stagger: delay / 1000 });
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          animate();
          observer.disconnect();
        }
      },
      { threshold },
    );
    observer.observe(container);

    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return (
    <Tag ref={containerRef as never} className={`${styles.root} ${className}`} aria-label={text}>
      {units.map((unit, index) =>
        unit.trim() === '' ? (
          <span key={index}>{unit}</span>
        ) : (
          <span key={index} className={styles.unit} aria-hidden="true">
            {unit}
          </span>
        ),
      )}
    </Tag>
  );
}
