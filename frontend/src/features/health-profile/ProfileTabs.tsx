/** Accessible tablist for the profile sections (roving focus, arrow-key navigation). */

import { useRef } from 'react';

import styles from './health-profile.module.css';

export interface ProfileTab {
  id: string;
  label: string;
  count?: number;
}

interface ProfileTabsProps {
  tabs: ProfileTab[];
  activeId: string;
  onSelect: (id: string) => void;
}

export function ProfileTabs({ tabs, activeId, onSelect }: ProfileTabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (offset === 0) {
      return;
    }
    event.preventDefault();
    const index = tabs.findIndex((tab) => tab.id === activeId);
    const next = tabs[(index + offset + tabs.length) % tabs.length];
    onSelect(next.id);
    listRef.current?.querySelector<HTMLButtonElement>(`#tab-${next.id}`)?.focus();
  }

  return (
    <div className={styles.tabs} role="tablist" aria-label="Health profile sections" ref={listRef} onKeyDown={onKeyDown}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            className={styles.tab}
            data-active={isActive}
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onSelect(tab.id)}
          >
            {tab.label}
            {tab.count !== undefined && <span className={styles.tabCount}>{tab.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
