/** Sticky app header - brand, primary nav (desktop + mobile), and the signed-in user chip. */

import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import logoDarkUrl from '@/assets/logo-icon-dark.png';
import { useTheme } from '@/components/ThemeProvider';
import { useAuth } from '@/features/auth';
import styles from './Header.module.css';

const NAV_ITEMS = [
  { to: '/prescriptions', label: 'Prescription Analyzer' },
  { to: '/profile', label: 'Health Profile' },
  { to: '/comparison', label: 'Report Comparison' },
  { to: '/meal-plan', label: 'Meal Planner' },
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

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      className={styles.themeToggle}
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? '\u2600\uFE0F' : '\u{1F319}'}
    </button>
  );
}

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { theme } = useTheme();

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link className={styles.brand} to="/" aria-label="HealthIQ home">
          <img src={theme === 'dark' ? logoDarkUrl : logoUrl} alt="" className={styles.logo} />
          <span className={styles.brandText}>
            Health<span className={styles.brandAccent}>IQ</span>
          </span>
        </Link>

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
          <ThemeToggle />
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
