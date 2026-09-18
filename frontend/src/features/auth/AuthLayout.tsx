import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import logoUrl from '@/assets/logo-icon.png';
import logoDarkUrl from '@/assets/logo-icon-dark.png';
import { useTheme } from '@/components/ThemeProvider';

import styles from './auth.module.css';

export function AuthLayout({ children }: { children: ReactNode }) {
  const { theme } = useTheme();

  return (
    <main className={styles.authLayout}>
      <Link className={styles.authBrand} to="/" aria-label="HealthIQ home">
        <img src={theme === 'dark' ? logoDarkUrl : logoUrl} alt="" />
        <span>HealthIQ</span>
      </Link>
      {children}
    </main>
  );
}