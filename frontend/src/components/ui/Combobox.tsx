/**
 * Searchable single/multi select following the WAI-ARIA combobox pattern
 * (`role="combobox"` + `aria-activedescendant` over a `role="listbox"` popup).
 *
 * `allowCustomValue` exists because the backend validates preference tokens structurally rather
 * than against a fixed allowlist, so a user may enter a value the curated list does not carry.
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react';

import styles from './Combobox.module.css';

interface ComboboxProps {
  label: string;
  options: string[];
  /** Always an array; a single-select combobox holds at most one entry. */
  value: string[];
  onChange: (next: string[]) => void;
  multiple?: boolean;
  allowCustomValue?: boolean;
  placeholder?: string;
  hint?: string;
  error?: string;
  id?: string;
}

export function Combobox({
  label,
  options,
  value,
  onChange,
  multiple = false,
  allowCustomValue = false,
  placeholder,
  hint,
  error,
  id,
}: ComboboxProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const listboxId = `${inputId}-listbox`;

  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const available = options.filter((option) => multiple || !value.includes(option));
    return needle ? available.filter((option) => option.toLowerCase().includes(needle)) : available;
  }, [options, query, value, multiple]);

  const trimmed = query.trim();
  const canCreate =
    allowCustomValue &&
    trimmed.length > 0 &&
    !options.some((option) => option.toLowerCase() === trimmed.toLowerCase()) &&
    !value.some((entry) => entry.toLowerCase() === trimmed.toLowerCase());

  const items = canCreate ? [...filtered, trimmed] : filtered;

  useEffect(() => {
    setActiveIndex(0);
  }, [query, isOpen]);

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, []);

  function select(option: string) {
    if (multiple) {
      onChange(value.includes(option) ? value.filter((entry) => entry !== option) : [...value, option]);
      setQuery('');
    } else {
      onChange([option]);
      setQuery('');
      setIsOpen(false);
    }
    inputRef.current?.focus();
  }

  function remove(option: string) {
    onChange(value.filter((entry) => entry !== option));
    inputRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        return;
      }
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex((current) => (items.length === 0 ? 0 : (current + step + items.length) % items.length));
      return;
    }

    if (event.key === 'Enter' && isOpen && items[activeIndex]) {
      event.preventDefault();
      select(items[activeIndex]);
      return;
    }

    if (event.key === 'Escape') {
      setIsOpen(false);
      return;
    }

    // Backspace on an empty query removes the last chip, the usual multi-select shortcut.
    if (event.key === 'Backspace' && query === '' && multiple && value.length > 0) {
      remove(value[value.length - 1]);
    }
  }

  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  const chips = multiple ? value : [];
  const singleValue = !multiple && value.length > 0 ? value[0] : '';

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>

      <div className={styles.wrapper} ref={wrapperRef}>
        <div
          className={[styles.control, error ? styles.controlError : ''].filter(Boolean).join(' ')}
          onClick={() => inputRef.current?.focus()}
role="presentation"
        >
          {chips.map((entry) => (
            <span key={entry} className={styles.chip}>
              {entry}
              <button
                type="button"
                className={styles.chipRemove}
                aria-label={`Remove ${entry}`}
                onClick={() => remove(entry)}
              >
                &times;
              </button>
            </span>
          ))}

          <input
            id={inputId}
            ref={inputRef}
            className={styles.input}
            type="text"
            role="combobox"
            autoComplete="off"
            aria-expanded={isOpen}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={isOpen && items[activeIndex] ? `${inputId}-option-${activeIndex}` : undefined}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            placeholder={chips.length > 0 ? undefined : placeholder}
            value={isOpen || multiple ? query : singleValue || query}
            onChange={(event) => {
              setQuery(event.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={onKeyDown}
          />

          <button
            type="button"
            className={styles.toggle}
            tabIndex={-1}
            aria-label={`${isOpen ? 'Close' : 'Open'} ${label} options`}
            onClick={() => {
              setIsOpen((open) => !open);
              inputRef.current?.focus();
            }}
          >
            &#9662;
          </button>
        </div>

        {isOpen && (
          <ul className={styles.listbox} id={listboxId} role="listbox" aria-label={label}>
            {items.length === 0 && <li className={styles.empty}>No matches</li>}
            {items.map((option, index) => (
              <li
                key={option}
                id={`${inputId}-option-${index}`}
                className={styles.option}
                role="option"
                aria-selected={value.includes(option)}
                data-active={index === activeIndex}
                onPointerDown={(event) => {
                  event.preventDefault();
                  select(option);
                }}
              >
                {canCreate && index === items.length - 1 ? `Add "${option}"` : option}
              </li>
            ))}
          </ul>
        )}
      </div>

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
