/** Sticky app header - brand, primary nav (desktop + mobile), and the signed-in user chip. */

import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import { useAuth } from '@/features/auth';
import styles from './Header.module.css';

// Labels name the outcome a user gets, not the internal feature name; the description is exposed
// as a tooltip on desktop and as a second line in the mobile menu.
const NAV_ITEMS = [
  { to: '/', label: 'Home', description: 'All your health tools in one place' },
  { to: '/profile', label: 'Health Report', description: 'Understand your lab results and who to consult' },
  {
    to: '/prescriptions',
    label: 'Prescription Check',
    description: 'Check a prescription for lower-cost alternatives',
  },
  { to: '/comparison', label: 'Report Trends', description: 'See what changed between two reports' },
  { to: '/meal-plan', label: 'Meal Plan', description: 'Food guidance built around your results' },
];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? parts[0]?.[1] ?? '');
}

function AccountChip() {
  const { account, isLoading, logout } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!account) {
    return (
      <Link className={styles.signInLink} to="/login">
        Sign in
      </Link>
    );
  }

  const label = account.displayName ?? account.username;

  return (
    <div className={styles.userChip} title={label}>
      <span className={styles.avatar} aria-hidden="true">
        {initials(label).toUpperCase()}
      </span>
      <span className={styles.userName}>{label}</span>
      <button type="button" className={styles.signOutButton} onClick={() => void logout()}>
        Sign out
      </button>
    </div>
  );
}

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link className={styles.brand} to="/" aria-label="HealthIQ home">
          <img src={logoUrl} alt="" className={styles.logo} />
          <span className={styles.brandText}>
            Health<span className={styles.brandAccent}>IQ</span>
          </span>
        </Link>

        <nav className={styles.navDesktop} aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              title={item.description}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className={styles.rightSlot}>
          <AccountChip />

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
              end={item.to === '/'}
              onClick={() => setIsMenuOpen(false)}
              className={({ isActive }) => `${styles.navLinkMobile} ${isActive ? styles.navLinkActive : ''}`}
            >
              {item.label}
              <span className={styles.navDescription}>{item.description}</span>
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
