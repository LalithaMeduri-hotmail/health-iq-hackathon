/**
 * Step 2: the confirmation grid. Every analyzed run passes through here - a clean digital PDF as
 * much as a low-confidence photo - so nothing reaches the alternatives step without the user
 * cross-checking the medicine list (frontend.instructions.md safety UX).
 */

import { useState } from 'react';

import { Badge, Button, Card, Input, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui';

import styles from './prescription.module.css';
import type { MedicineCorrectionInput, MedicineEntity } from './types';

interface ConfirmStepProps {
  items: MedicineEntity[];
  onSubmit: (corrections: MedicineCorrectionInput[]) => void;
  isPending: boolean;
}

export function ConfirmStep({ items, onSubmit, isPending }: ConfirmStepProps) {
  const [names, setNames] = useState<Record<string, string>>(
    Object.fromEntries(items.map((item) => [item.lineId, item.brandName ?? item.rawText])),
  );

  const unclearCount = items.filter((item) => item.needsUserConfirmation).length;
  const allNamed = items.every((item) => names[item.lineId]?.trim());

  return (
    <Card
      title="Check these medicines"
      subtitle={
        unclearCount > 0
          ? `We could not read ${unclearCount} line(s) with full confidence. Correct anything that is wrong, then confirm - we only look for alternatives once you do.`
          : 'Correct anything that is wrong, then confirm - we only look for alternatives once you do.'
      }
    >
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell scope="col">Line as read</TableHeaderCell>
            <TableHeaderCell scope="col">Medicine</TableHeaderCell>
            <TableHeaderCell scope="col">Strength</TableHeaderCell>
            <TableHeaderCell scope="col">Status</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.lineId}>
              <TableCell>{item.rawText}</TableCell>
              <TableCell>
                <Input
                  label={`Medicine name for ${item.rawText}`}
                  hideLabel
                  value={names[item.lineId] ?? ''}
                  onChange={(event) => setNames({ ...names, [item.lineId]: event.target.value })}
                />
              </TableCell>
              <TableCell>
                {item.strengthValue ?? '?'} {item.strengthUnit ?? ''}
              </TableCell>
              <TableCell>
                {item.needsUserConfirmation ? (
                  <Badge tone="warning">Needs confirmation</Badge>
                ) : (
                  <Badge tone="success">Confirmed</Badge>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className={styles.actions}>
        <Button
          type="button"
          size="lg"
          disabled={!allNamed}
          isLoading={isPending}
          onClick={() =>
            onSubmit(items.map((item) => ({ lineId: item.lineId, brandName: names[item.lineId].trim() })))
          }
        >
          Confirm &amp; find alternatives
        </Button>
      </div>
    </Card>
  );
}
