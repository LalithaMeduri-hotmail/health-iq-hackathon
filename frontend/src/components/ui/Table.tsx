/** Styled table primitives - compose with <Table><TableHead>/<TableBody><TableRow><TableCell>. */

import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react';

import styles from './Table.module.css';

export function Table({ className, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className={styles.scroller}>
      <table className={[styles.table, className].filter(Boolean).join(' ')} {...rest} />
    </div>
  );
}

export function TableHead(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={styles.head} {...props} />;
}

export function TableBody(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} />;
}

export function TableRow(props: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={styles.row} {...props} />;
}

export function TableHeaderCell(props: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={styles.headerCell} {...props} />;
}

export function TableCell(props: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={styles.cell} {...props} />;
}
