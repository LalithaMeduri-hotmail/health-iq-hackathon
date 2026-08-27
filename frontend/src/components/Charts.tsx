/**
 * Shared chart components (frontend.instructions.md - Recharts, colorblind-safe, labeled units).
 *
 * TODO(D4): line chart (repeated parameters), radar chart (by system), health-score gauge,
 * color-coded before/after table - see implementation-plan.md Section 5.4.
 */

export function TrendLineChart(_props: { data: Array<{ date: string; value: number }>; unit: string }) {
  return <div>TODO: trend line chart</div>;
}

export function SystemRadarChart(_props: { data: Array<{ system: string; score: number }> }) {
  return <div>TODO: system radar chart</div>;
}

export function HealthScoreGauge(_props: { score: number }) {
  return <div>TODO: health score gauge</div>;
}
