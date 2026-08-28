/** Accessible labeled text input with optional hint/error text. */

import { useId } from 'react';
import type { InputHTMLAttributes } from 'react';

import styles from './FormField.module.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  hideLabel?: boolean;
}

export function Input({ label, hint, error, hideLabel, id, className, ...rest }: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className={styles.field}>
      <label className={hideLabel ? 'visually-hidden' : styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input
        id={inputId}
        className={[styles.control, error ? styles.controlError : '', className].filter(Boolean).join(' ')}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        {...rest}
      />
      {error && (
        <p className={styles.error} id={`${inputId}-error`}>
          {error}
        </p>
      )}
      {!error && hint && (
        <p className={styles.hint} id={`${inputId}-hint`}>
          {hint}
        </p>
      )}
    </div>
  );
}
