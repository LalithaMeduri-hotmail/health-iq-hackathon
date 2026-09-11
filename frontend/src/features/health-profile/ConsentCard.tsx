/** Consent record - shown on the main profile page because it governs every panel below it. */

import { Badge, Card } from '@/components/ui';

import styles from './health-profile.module.css';
import type { Consent } from './types';

export function ConsentCard({ consent }: { consent: Consent }) {
  return (
    <Card
      className={styles.card}
      title="Consent record"
      subtitle="Captured the first time you analyze a report, and shown here in full."
    >
      {consent.version ? (
        <>
          <div className={styles.chips}>
            <Badge tone="success">Accepted v{consent.version}</Badge>
            {consent.purposes.map((purpose) => (
              <Badge key={purpose} tone="info">
                {purpose}
              </Badge>
            ))}
          </div>
          <p className={styles.meta}>Accepted on {new Date(consent.acceptedAt!).toLocaleString()}.</p>
        </>
      ) : (
        <p className={styles.meta}>No consent recorded yet. It is captured the first time you analyze a report.</p>
      )}
    </Card>
  );
}
