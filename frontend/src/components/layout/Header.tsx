/**
 * Sticky app header - brand, primary nav (desktop + mobile), and the signed-in user menu.
 *
 * The feature nav, the user menu, and the mobile menu are rendered only for a signed-in account:
 * every one of those destinations needs a patient profile to act on, so offering them to a
 * visitor on the landing page just routes them to a sign-in wall.
 */

import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import logoDarkUrl from '@/assets/logo-icon-dark.png';
import { useTheme } from '@/components/ThemeProvider';
import { useAuth } from '@/features/auth';
import { ProfileSelector } from '@/features/patient-profiles';
import styles from './Header.module.css';

const NAV_ITEMS = [
  { to: '/prescriptions', label: 'Prescription Analyzer' },
  { to: '/profile', label: 'Health Profile' },
  { to: '/comparison', label: 'Report Comparison' },
  { to: '/meal-plan', label: 'Meal Planner' },
];

function SignInLink() {
  const { account, isLoading } = useAuth();

  if (isLoading || account) {
    return null;
  }

  return (
    <Link className={styles.signInLink} to="/login">
      Sign in
    </Link>
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
  const { account, isLoading } = useAuth();

  // Stay closed while the session resolves, so the nav does not flash in and out on first paint.
  const isSignedIn = !isLoading && account !== null;

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link className={styles.brand} to="/" aria-label="HealthIQ home">
          <img src={theme === 'dark' ? logoDarkUrl : logoUrl} alt="" className={styles.logo} />
          <span className={styles.brandText}>
            Health<span className={styles.brandAccent}>IQ</span>
          </span>
        </Link>

        {isSignedIn && (
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
        )}

        <div className={styles.rightSlot}>
          <ThemeToggle />
          <SignInLink />
          {isSignedIn && <ProfileSelector />}

          {isSignedIn && (
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
          )}
        </div>
      </div>

      {isSignedIn && isMenuOpen && (
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
