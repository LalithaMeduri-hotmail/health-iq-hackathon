/** Sticky app header - brand, primary nav (desktop + mobile), and the demo user chip. */

import { useState } from 'react';
import { NavLink } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import styles from './Header.module.css';

const NAV_ITEMS = [
  { to: '/prescriptions', label: 'Prescription Analyzer' },
  { to: '/profile', label: 'Health Profile' },
  { to: '/comparison', label: 'Report Comparison' },
  { to: '/meal-plan', label: 'Meal Planner' },
];

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <a className={styles.brand} href="/prescriptions" aria-label="HealthIQ home">
          <img src={logoUrl} alt="" className={styles.logo} />
          <span className={styles.brandText}>
            Health<span className={styles.brandAccent}>IQ</span>
          </span>
        </a>

        <nav className={styles.navDesktop} aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className={styles.rightSlot}>
          <div className={styles.userChip} title="Demo mode - Entra sign-in not yet wired">
            <span className={styles.avatar} aria-hidden="true">
              DU
            </span>
            <span className={styles.userName}>Demo User</span>
          </div>

          <button
            type="button"
            className={styles.menuButton}
            aria-expanded={isMenuOpen}
            aria-controls="primary-nav-mobile"
            aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            onClick={() => setIsMenuOpen((open) => !open)}
          >
            <span className={`${styles.menuIcon} ${isMenuOpen ? styles.menuIconOpen : ''}`} aria-hidden="true" />
          </button>
        </div>
      </div>

      {isMenuOpen && (
        <nav id="primary-nav-mobile" className={styles.navMobile} aria-label="Primary mobile">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setIsMenuOpen(false)}
              className={({ isActive }) => `${styles.navLinkMobile} ${isActive ? styles.navLinkActive : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
