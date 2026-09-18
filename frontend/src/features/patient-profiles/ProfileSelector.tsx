/**
 * Header user menu: the single control for who the app is acting for and who is signed in.
 *
 * The active profile stays on the button face rather than inside the menu, because every other
 * screen is scoped to it - a user who misreads this is looking at the wrong person's health data.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '@/features/auth';

import { useActiveProfile } from './ActiveProfileContext';
import styles from './patientProfiles.module.css';
import type { PatientProfile } from './types';

const RELATIONSHIP_LABELS: Record<string, string> = {
  self: 'You',
  spouse: 'Spouse',
  parent: 'Parent',
  child: 'Child',
  sibling: 'Sibling',
  grandparent: 'Grandparent',
  dependent: 'Dependent',
  other: 'In your care',
};

export function relationshipLabel(profile: PatientProfile): string {
  return RELATIONSHIP_LABELS[profile.relationshipToAccountOwner] ?? 'In your care';
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const second = parts[1]?.[0] ?? parts[0]?.[1] ?? '';
  return (first + second).toUpperCase();
}

export function ProfileSelector() {
  const { profiles, activeProfile, setActiveProfile } = useActiveProfile();
  const { account, isLoading: isAuthLoading, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen]);

  if (isAuthLoading || !account) {
    return null;
  }

  const selectable = profiles.filter((profile) => profile.status === 'active');
  const accountName = account.displayName ?? account.username;
  const buttonName = activeProfile?.displayName ?? accountName;

  return (
    <div className={styles.selector} ref={containerRef}>
      <button
        type="button"
        className={styles.selectorButton}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className={styles.selectorAvatar} aria-hidden="true">
          {initials(buttonName)}
        </span>
        <span className={styles.selectorLabel}>
          <span className={styles.selectorName}>{buttonName}</span>
          <span className={styles.selectorRelation}>
            {activeProfile ? relationshipLabel(activeProfile) : 'Your account'}
          </span>
        </span>
        <span className={styles.selectorCaret} aria-hidden="true">
          &#9662;
        </span>
      </button>

      {isOpen && (
        <div className={styles.menu} role="menu" aria-label="Account and patient profiles">
          <p className={styles.menuHint}>Signed in as {accountName}</p>
          {selectable.length > 0 && <p className={styles.menuHint}>Viewing health records for</p>}
          {selectable.map((profile) => (
            <button
              key={profile.id}
              type="button"
              role="menuitemradio"
              aria-checked={profile.id === activeProfile?.id}
              className={`${styles.menuItem} ${
                profile.id === activeProfile?.id ? styles.menuItemActive : ''
              }`}
              onClick={() => {
                setActiveProfile(profile.id);
                setIsOpen(false);
              }}
            >
              <span className={styles.selectorAvatar} aria-hidden="true">
                {initials(profile.displayName)}
              </span>
              <span className={styles.selectorLabel}>
                <span className={styles.selectorName}>{profile.displayName}</span>
                <span className={styles.selectorRelation}>{relationshipLabel(profile)}</span>
              </span>
            </button>
          ))}

          <div className={styles.menuDivider} />
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => {
              setIsOpen(false);
              navigate('/profiles');
            }}
          >
            Manage profiles
          </button>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => {
              setIsOpen(false);
              void logout();
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
