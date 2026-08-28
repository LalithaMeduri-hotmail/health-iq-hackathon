/** Top-level page shell: sticky header, routed content region, safety banner, footer. */

import type { ReactNode } from 'react';

import { Disclaimer } from '@/components/Disclaimer';

import { Footer } from './Footer';
import { Header } from './Header';
import styles from './AppShell.module.css';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <>
      <Header />
      <main className={styles.main}>
        <div className={`container ${styles.content}`}>{children}</div>
      </main>
      <Disclaimer />
      <Footer />
    </>
  );
}
