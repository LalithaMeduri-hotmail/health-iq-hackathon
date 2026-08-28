/**
 * Shared disclaimer footer (frontend.instructions.md - every feature view renders the shared
 * Disclaimer component; never hide or omit it). Rendered once, globally, by `AppShell`.
 */

import styles from './Disclaimer.module.css';

const DISCLAIMER_TEXT =
  'This is a health information and doctor-collaboration assistant. It does not diagnose, ' +
  'prescribe, or replace clinical judgment. Any medicine alternative or health action must be ' +
  'reviewed by a qualified healthcare professional.';

export function Disclaimer({ text = DISCLAIMER_TEXT }: { text?: string }) {
  return (
    <div className={styles.banner} role="contentinfo">
      <div className={`container ${styles.inner}`}>
        <span className={styles.icon} aria-hidden="true">
          i
        </span>
        <p className={styles.text}>{text}</p>
      </div>
    </div>
  );
}
