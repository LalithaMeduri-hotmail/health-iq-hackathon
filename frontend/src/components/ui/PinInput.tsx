/** Big square-box PIN entry (4 digits) with auto-advance, backspace, arrow-key, and paste support. */

import { useRef } from 'react';
import type { ClipboardEvent, KeyboardEvent } from 'react';

import styles from './PinInput.module.css';

interface PinInputProps {
  length?: number;
  value: string;
  onChange: (value: string) => void;
  label: string;
  error?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}

export function PinInput({ length = 4, value, onChange, label, error, autoFocus, disabled }: PinInputProps) {
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length }, (_, index) => value[index] ?? '');
  const labelId = `pin-input-label-${label.replace(/\s+/g, '-').toLowerCase()}`;

  function setDigit(index: number, digit: string) {
    const next = digits.slice();
    next[index] = digit;
    onChange(next.join(''));
  }

  function handleChange(index: number, raw: string) {
    const digit = raw.replace(/\D/g, '').slice(-1);
    setDigit(index, digit);
    if (digit && index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
      setDigit(index - 1, '');
    } else if (event.key === 'ArrowLeft' && index > 0) {
      inputsRef.current[index - 1]?.focus();
    } else if (event.key === 'ArrowRight' && index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    if (!pasted) {
      return;
    }
    event.preventDefault();
    onChange(pasted);
    inputsRef.current[Math.min(pasted.length, length - 1)]?.focus();
  }

  return (
    <div className={styles.wrapper}>
      <span className={styles.label} id={labelId}>
        {label}
      </span>
      <div
        className={styles.boxes}
        role="group"
        aria-labelledby={labelId}
        aria-describedby={error ? `${labelId}-error` : undefined}
      >
        {digits.map((digit, index) => (
          <input
            key={index}
            ref={(element) => {
              inputsRef.current[index] = element;
            }}
            type="password"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={1}
            className={`${styles.box} ${error ? styles.boxError : ''}`}
            value={digit}
            disabled={disabled}
            autoFocus={autoFocus && index === 0}
            aria-label={`${label}, digit ${index + 1} of ${length}`}
            onChange={(event) => handleChange(index, event.target.value)}
            onKeyDown={(event) => handleKeyDown(index, event)}
            onPaste={handlePaste}
            onFocus={(event) => event.target.select()}
          />
        ))}
      </div>
      {error && (
        <p className={styles.error} id={`${labelId}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}
