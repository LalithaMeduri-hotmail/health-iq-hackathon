/** Premium page header - gradient icon badge + eyebrow + title + subtitle, used atop every route. */

import type { ReactNode } from 'react';

import styles from './PageHeader.module.css';

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, icon, actions }: PageHeaderProps) {
  return (
    <div className={styles.header}>
      <div className={styles.heading}>
        {icon && <span className={styles.iconBadge}>{icon}</span>}
        <div>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 className={styles.title}>{title}</h1>
          {description && <p className={styles.description}>{description}</p>}
        </div>
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}
