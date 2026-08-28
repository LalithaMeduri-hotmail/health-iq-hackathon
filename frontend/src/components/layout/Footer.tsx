/** Site footer - brand recap, quick nav, contact/about, social placeholders, compliance line. */

import logoUrl from '@/assets/logo-icon.png';
import styles from './Footer.module.css';

const PRODUCT_LINKS = [
  { to: '/prescriptions', label: 'Prescription Analyzer' },
  { to: '/profile', label: 'Health Profile' },
  { to: '/comparison', label: 'Report Comparison' },
  { to: '/meal-plan', label: 'Meal Planner' },
];

const COMPANY_LINKS = ['About HealthIQ', 'Contact support', 'Privacy policy', 'Terms of use'];

const SOCIAL_PLACEHOLDERS = [
  { label: 'X (Twitter)', glyph: '\u{1D54F}' },
  { label: 'LinkedIn', glyph: 'in' },
  { label: 'GitHub', glyph: 'gh' },
];

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.grid}`}>
        <div className={styles.brandColumn}>
          <div className={styles.brandRow}>
            <img src={logoUrl} alt="" className={styles.logo} />
            <span className={styles.brandText}>
              Health<span className={styles.brandAccent}>IQ</span>
            </span>
          </div>
          <p className={styles.tagline}>Smarter health. Better you.</p>
          <div className={styles.socialRow} aria-label="Social links (coming soon)">
            {SOCIAL_PLACEHOLDERS.map((social) => (
              <span key={social.label} className={styles.socialIcon} title={`${social.label} - coming soon`}>
                {social.glyph}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h3 className={styles.heading}>Product</h3>
          <ul className={styles.linkList}>
            {PRODUCT_LINKS.map((link) => (
              <li key={link.to}>
                <a href={link.to}>{link.label}</a>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className={styles.heading}>Company</h3>
          <ul className={styles.linkList}>
            {COMPANY_LINKS.map((label) => (
              <li key={label}>
                <span className={styles.linkPlaceholder} title="Coming soon">
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className={styles.bottomBar}>
        <div className="container">
          <p className={styles.copyright}>
            &copy; {new Date().getFullYear()} HealthIQ. Built for a hackathon demo - not a certified medical device.
          </p>
        </div>
      </div>
    </footer>
  );
}
