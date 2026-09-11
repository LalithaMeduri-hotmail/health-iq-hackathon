/** Compact table of lab values with the reference range that defined their status. */

import { Badge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui';

import { referenceRange, statusLabel, statusTone } from './status';
import styles from './health-profile.module.css';
import type { LabParameter } from './types';

interface ParameterTableProps {
  parameters: LabParameter[];
}

export function ParameterTable({ parameters }: ParameterTableProps) {
  if (parameters.length === 0) {
    return <p className={styles.meta}>Every measured value sits inside its typical range.</p>;
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell scope="col">Parameter</TableHeaderCell>
          <TableHeaderCell scope="col">Value</TableHeaderCell>
          <TableHeaderCell scope="col">Typical range</TableHeaderCell>
          <TableHeaderCell scope="col">Status</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {parameters.map((parameter) => (
          <TableRow key={parameter.canonicalKey}>
            <TableCell>{parameter.displayName}</TableCell>
            <TableCell>
              {parameter.value} {parameter.unit}
            </TableCell>
            <TableCell>{referenceRange(parameter)}</TableCell>
            <TableCell>
              <Badge tone={statusTone(parameter.status)}>{statusLabel(parameter.status)}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
