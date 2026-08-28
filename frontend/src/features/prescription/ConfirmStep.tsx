/**
 * Step 2: confirmation grid for low-confidence OCR lines (`422 low-confidence-ocr`).
 * Forces user confirmation before alternatives are requested (frontend.instructions.md).
 */

import { useState } from 'react';

import { Badge, Button, Card, Input, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui';

import type { MedicineEntity } from './types';

interface ConfirmStepProps {
  items: MedicineEntity[];
  onSubmit: (corrections: { lineId: string; brandName: string }[]) => void;
  isPending: boolean;
}

export function ConfirmStep({ items, onSubmit, isPending }: ConfirmStepProps) {
  const flagged = items.filter((item) => item.needsUserConfirmation);
  const [corrections, setCorrections] = useState<Record<string, string>>(
    Object.fromEntries(flagged.map((item) => [item.lineId, item.brandName ?? ''])),
  );

  const allFilled = flagged.every((item) => corrections[item.lineId]?.trim());

  return (
    <Card
      title="Please confirm these medicines"
      subtitle="We could not read some lines with full confidence. Please confirm or correct the medicine name before we look for doctor-reviewable alternatives."
    >
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Line as read</TableHeaderCell>
            <TableHeaderCell>Medicine</TableHeaderCell>
            <TableHeaderCell>Strength</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.lineId}>
              <TableCell>{item.rawText}</TableCell>
              <TableCell>
                {item.needsUserConfirmation ? (
                  <Input
                    label={`Medicine name for ${item.lineId}`}
                    hideLabel
                    value={corrections[item.lineId] ?? ''}
                    onChange={(event) => setCorrections({ ...corrections, [item.lineId]: event.target.value })}
                  />
                ) : (
                  item.brandName
                )}
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

      <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          type="button"
          size="lg"
          disabled={!allFilled}
          isLoading={isPending}
          onClick={() =>
            onSubmit(flagged.map((item) => ({ lineId: item.lineId, brandName: corrections[item.lineId] })))
          }
        >
          Confirm & continue
        </Button>
      </div>
    </Card>
  );
}
