/**
 * Shared chart components (frontend.instructions.md - Recharts, colorblind-safe, labeled units).
 *
 * TODO(D4): radar chart (by system) and health-score gauge need `ReportSummary.systemCards`
 * from the report-analysis feature - see implementation-plan.md Section 5.4.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface TrendLineChartProps {
  data: Array<{ date: string; value: number }>;
  unit: string;
  label?: string;
  refLow?: number | null;
  refHigh?: number | null;
}

export function TrendLineChart({ data, unit, label, refLow, refHigh }: TrendLineChartProps) {
  const title = label ? `${label} trend in ${unit}` : `Trend in ${unit}`;
  const hasBand = refLow !== null && refLow !== undefined && refHigh !== null && refHigh !== undefined;

  return (
    <figure role="img" aria-label={title} style={{ margin: 0 }}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          {hasBand && <ReferenceArea y1={refLow} y2={refHigh} fill="#0072b2" fillOpacity={0.08} />}
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} width={56} label={{ value: unit, angle: -90, position: 'insideLeft' }} />
          <Tooltip formatter={(value: number) => [`${value} ${unit}`, label ?? 'Value']} />
          <Line type="monotone" dataKey="value" stroke="#0072b2" strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}

export function SystemRadarChart(_props: { data: Array<{ system: string; score: number }> }) {
  return <div>TODO: system radar chart</div>;
}

export function HealthScoreGauge(_props: { score: number }) {
  return <div>TODO: health score gauge</div>;
}
