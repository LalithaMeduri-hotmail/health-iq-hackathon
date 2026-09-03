/**
 * Shared chart components (frontend.instructions.md - Recharts, colorblind-safe, labeled units).
 *
 * TODO(D4): radar chart (by system) needs `ReportSummary.systemCards` from the report-analysis
 * feature - see implementation-plan.md Section 5.4.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
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

// Colorblind-safe (Okabe-Ito): blue / orange / vermillion rather than green / amber / red.
const GAUGE_BANDS = [
  { min: 80, fill: '#0072b2', label: 'most values inside the typical range' },
  { min: 60, fill: '#e69f00', label: 'some values outside the typical range' },
  { min: 0, fill: '#d55e00', label: 'several values outside the typical range' },
];

interface HealthScoreGaugeProps {
  score: number;
  reportDate?: string;
}

export function HealthScoreGauge({ score, reportDate }: HealthScoreGaugeProps) {
  const bounded = Math.max(0, Math.min(100, score));
  const band = GAUGE_BANDS.find((candidate) => bounded >= candidate.min) ?? GAUGE_BANDS[GAUGE_BANDS.length - 1];
  const caption = `Indicator score ${bounded} out of 100: ${band.label}`;

  return (
    <figure role="img" aria-label={caption} style={{ margin: 0, position: 'relative' }}>
      <ResponsiveContainer width="100%" height={200}>
        <RadialBarChart
          data={[{ value: bounded }]}
          innerRadius="72%"
          outerRadius="100%"
          startAngle={210}
          endAngle={-30}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar dataKey="value" fill={band.fill} background cornerRadius={8} isAnimationActive={false} />
        </RadialBarChart>
      </ResponsiveContainer>
      <figcaption
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'none',
        }}
      >
        <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>{bounded}</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>out of 100</span>
        {reportDate && (
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>as of {reportDate}</span>
        )}
      </figcaption>
    </figure>
  );
}
