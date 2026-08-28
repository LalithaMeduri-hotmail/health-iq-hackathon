/** Recoverable error banner - always pairs a plain-language message with a retry action. */

import type { ReactNode } from 'react';

import styles from './ErrorState.module.css';
import { Button } from './Button';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  icon?: ReactNode;
}

export function ErrorState({ message, onRetry, retryLabel = 'Try again', icon }: ErrorStateProps) {
  return (
    <div className={styles.wrapper} role="alert">
      <span className={styles.icon} aria-hidden="true">
        {icon ?? '!'}
      </span>
      <span className={styles.message}>{message}</span>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
