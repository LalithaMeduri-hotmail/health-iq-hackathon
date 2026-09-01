/**
 * Report Comparison feature root - pick two reports from history or upload two files ->
 * color-coded before/after table -> trend chart -> narrative -> shareable doctor PDF
 * (FR3.1-FR3.6 plus the share flow in implementation-plan.md Section 5.2/5.3).
 */

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { TrendLineChart } from '@/components/Charts';
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/ui';
import { Button } from '@/components/ui';
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui';
import { ApiError, absoluteApiUrl } from '@/lib/apiClient';

import { analyzeReport, compareReports, fetchReports, generateSharePdf } from './api';
import styles from './report-comparison.module.css';
import type { BadgeTone } from '@/components/ui';
import type { ChangeBucket, ChangedParameter, ComparisonResult, PdfGenerateResponse } from './types';

type Source = 'history' | 'upload';

const BUCKET_ORDER: ChangeBucket[] = ['worsened', 'newlyAbnormal', 'improved', 'unchanged', 'missing'];

const BUCKET_LABELS: Record<ChangeBucket, string> = {
  worsened: 'Moved away from range',
  newlyAbnormal: 'Newly outside range',
  improved: 'Moved toward range',
  unchanged: 'About the same',
  missing: 'Not repeated',
};

const BUCKET_TONES: Record<ChangeBucket, BadgeTone> = {
  worsened: 'danger',
  newlyAbnormal: 'warning',
  improved: 'success',
  unchanged: 'neutral',
  missing: 'info',
};

function formatValue(value: number | null, unit: string): string {
  return value === null ? '--' : `${value} ${unit}`;
}

function formatChange(pctChange: number | null): string {
  if (pctChange === null) {
    return '--';
  }
  return `${pctChange > 0 ? '+' : ''}${pctChange}%`;
}

function flattenRows(result: ComparisonResult): Array<{ bucket: ChangeBucket; parameter: ChangedParameter }> {
  return BUCKET_ORDER.flatMap((bucket) => result[bucket].map((parameter) => ({ bucket, parameter })));
}

/** A move can be large yet stay inside the range - say so instead of calling it unchanged. */
function verdict(bucket: ChangeBucket, parameter: ChangedParameter): { label: string; tone: BadgeTone } {
  const moved = Math.abs(parameter.pctChange ?? 0) >= 5;
  if (bucket === 'unchanged' && moved) {
    return parameter.status === 'unknown'
      ? { label: 'Changed - no range on file', tone: 'info' }
      : { label: 'Changed - still in range', tone: 'info' };
  }
  return { label: BUCKET_LABELS[bucket], tone: BUCKET_TONES[bucket] };
}

export function ReportComparisonFeature() {
  const queryClient = useQueryClient();
  const reportsQuery = useQuery({ queryKey: ['reports'], queryFn: fetchReports });
  const reports = useMemo(() => reportsQuery.data?.data.reports ?? [], [reportsQuery.data]);

  const [source, setSource] = useState<Source>('history');
  const [oldReportId, setOldReportId] = useState('');
  const [currentReportId, setCurrentReportId] = useState('');
  const [olderFile, setOlderFile] = useState<File | null>(null);
  const [newerFile, setNewerFile] = useState<File | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [share, setShare] = useState<PdfGenerateResponse | null>(null);
  const [trendKey, setTrendKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  // Reports arrive newest first, so the most recent pair is the useful default.
  useEffect(() => {
    if (reports.length >= 2 && !currentReportId && !oldReportId) {
      setCurrentReportId(reports[0].reportId);
      setOldReportId(reports[1].reportId);
    }
  }, [reports, currentReportId, oldReportId]);

  function applyResult(comparison: ComparisonResult) {
    setErrorMessage(null);
    setNoticeMessage(null);
    setShare(null);
    setResult(comparison);
    setTrendKey(Object.keys(comparison.trendSeries)[0] ?? null);
  }

  function handleError(error: unknown, fallback: string) {
    setResult(null);
    setErrorMessage(error instanceof ApiError ? error.problem.detail : fallback);
  }

  const compareMutation = useMutation({
    mutationFn: () => compareReports(oldReportId, currentReportId),
    onSuccess: (response) => applyResult(response.data),
    onError: (error) => handleError(error, 'Something went wrong while comparing these reports.'),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const older = await analyzeReport(olderFile!);
      const newer = await analyzeReport(newerFile!);
      const undated = [older, newer].filter((response) =>
        response.safety.notes.includes('report-date-not-detected'),
      ).length;
      return { comparison: await compareReports(older.data.reportId, newer.data.reportId), undated };
    },
    onSuccess: ({ comparison, undated }) => {
      applyResult(comparison.data);
      setNoticeMessage(
        undated > 0
          ? `No report date was printed on ${undated === 2 ? 'either file' : 'one file'}, so today's date was used instead.`
          : null,
      );
      void queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
    onError: (error) => handleError(error, 'Could not read one of those reports. Please try another file.'),
  });

  const shareMutation = useMutation({
    mutationFn: () => generateSharePdf(result!.runId),
    onSuccess: (response) => setShare(response.data),
    onError: (error) => setErrorMessage(
      error instanceof ApiError ? error.problem.detail : 'Could not build the doctor PDF right now.',
    ),
  });

  const isComparing = compareMutation.isPending || uploadMutation.isPending;
  const trendKeys = result ? Object.keys(result.trendSeries) : [];
  const trendPoints = result && trendKey ? (result.trendSeries[trendKey] ?? []) : [];
  const trendParameter = result
    ? flattenRows(result).find((row) => row.parameter.canonicalKey === trendKey)?.parameter
    : undefined;

  return (
    <section aria-label="Report Comparison">
      <PageHeader
        eyebrow="AI-assisted"
        title="Report Comparison Engine"
        description="See how your lab parameters have changed over time, with plain-language, sourced explanations."
        icon={<span aria-hidden="true">&#128202;</span>}
      />

      <div className={styles.chips} role="group" aria-label="Choose where the reports come from">
        <button
          type="button"
          className={styles.chip}
          data-active={source === 'history'}
          aria-pressed={source === 'history'}
          onClick={() => setSource('history')}
        >
          From history
        </button>
        <button
          type="button"
          className={styles.chip}
          data-active={source === 'upload'}
          aria-pressed={source === 'upload'}
          onClick={() => setSource('upload')}
        >
          Compare two reports
        </button>
      </div>

      {source === 'history' && reportsQuery.isLoading && <LoadingState message="Loading your report history..." />}

      {source === 'history' && reportsQuery.isError && (
        <ErrorState message="Could not load your report history." onRetry={() => reportsQuery.refetch()} />
      )}

      {source === 'history' && !reportsQuery.isLoading && !reportsQuery.isError && reports.length < 2 && (
        <EmptyState
          icon={<span aria-hidden="true">&#128202;</span>}
          title="Two reports are needed for a comparison"
          description="Upload two lab reports using the option above and they will show up here as a before/after comparison."
        />
      )}

      {source === 'history' && reports.length >= 2 && (
        <Card title="Pick two reports" subtitle="Compare an older report against a more recent one.">
          <div className={styles.picker}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="old-report">
                Older report
              </label>
              <select
                id="old-report"
                className={styles.select}
                value={oldReportId}
                onChange={(event) => setOldReportId(event.target.value)}
              >
                {reports.map((report) => (
                  <option key={report.reportId} value={report.reportId}>
                    {report.reportDate} - {report.parameterCount} parameters ({report.abnormalCount} outside range)
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="current-report">
                Newer report
              </label>
              <select
                id="current-report"
                className={styles.select}
                value={currentReportId}
                onChange={(event) => setCurrentReportId(event.target.value)}
              >
                {reports.map((report) => (
                  <option key={report.reportId} value={report.reportId}>
                    {report.reportDate} - {report.parameterCount} parameters ({report.abnormalCount} outside range)
                  </option>
                ))}
              </select>
            </div>

            <Button
              onClick={() => compareMutation.mutate()}
              isLoading={compareMutation.isPending}
              disabled={!oldReportId || !currentReportId || oldReportId === currentReportId}
            >
              Compare
            </Button>
          </div>
        </Card>
      )}

      {source === 'upload' && (
        <Card
          title="Upload two lab reports"
          subtitle="PDF, JPG, PNG or HEIC, up to 10 MB each. Both are read, normalized, and then compared."
        >
          <div className={styles.picker}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="older-file">
                Older report file
              </label>
              <input
                id="older-file"
                className={styles.select}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.heic"
                onChange={(event) => setOlderFile(event.target.files?.[0] ?? null)}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="newer-file">
                Newer report file
              </label>
              <input
                id="newer-file"
                className={styles.select}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.heic"
                onChange={(event) => setNewerFile(event.target.files?.[0] ?? null)}
              />
            </div>

            <Button
              onClick={() => uploadMutation.mutate()}
              isLoading={uploadMutation.isPending}
              disabled={!olderFile || !newerFile}
            >
              Analyze and compare
            </Button>
          </div>
        </Card>
      )}

      {errorMessage && (
        <ErrorState message={errorMessage} onRetry={() => setErrorMessage(null)} retryLabel="Dismiss" />
      )}

      {noticeMessage && (
        <ErrorState
          icon={<span aria-hidden="true">i</span>}
          message={noticeMessage}
          onRetry={() => setNoticeMessage(null)}
          retryLabel="Dismiss"
        />
      )}

      {isComparing && <LoadingState message="Reading and comparing your reports..." />}

      {result && (
        <>
          <Card
            className={styles.resultCard}
            title={`${result.oldReportDate} to ${result.currentReportDate}`}
            subtitle="Every verdict below is calculated from your values against the typical reference range."
          >
            <div className={styles.summary}>
              {BUCKET_ORDER.map((bucket) => (
                <Badge key={bucket} tone={BUCKET_TONES[bucket]}>
                  {BUCKET_LABELS[bucket]}: {result[bucket].length}
                </Badge>
              ))}
            </div>

            <Table>
              <caption className={styles.caption}>Before and after values for every aligned parameter</caption>
              <TableHead>
                <TableRow>
                  <TableHeaderCell scope="col">Parameter</TableHeaderCell>
                  <TableHeaderCell scope="col">{result.oldReportDate}</TableHeaderCell>
                  <TableHeaderCell scope="col">{result.currentReportDate}</TableHeaderCell>
                  <TableHeaderCell scope="col">Change</TableHeaderCell>
                  <TableHeaderCell scope="col">Verdict</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {flattenRows(result).map(({ bucket, parameter }) => (
                  <TableRow key={parameter.canonicalKey}>
                    <TableCell>{parameter.displayName}</TableCell>
                    <TableCell>{formatValue(parameter.old, parameter.unit)}</TableCell>
                    <TableCell>{formatValue(parameter.current, parameter.unit)}</TableCell>
                    <TableCell>{formatChange(parameter.pctChange)}</TableCell>
                    <TableCell>
                      <Badge tone={verdict(bucket, parameter).tone}>{verdict(bucket, parameter).label}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {trendKeys.length > 0 && (
            <Card className={styles.resultCard} title="Trend over time" subtitle="Every report on record for this parameter.">
              <div className={styles.chips} role="group" aria-label="Choose a parameter to chart">
                {trendKeys.map((key) => (
                  <button
                    key={key}
                    type="button"
                    className={styles.chip}
                    data-active={key === trendKey}
                    aria-pressed={key === trendKey}
                    onClick={() => setTrendKey(key)}
                  >
                    {key}
                  </button>
                ))}
              </div>
              <TrendLineChart
                data={trendPoints.map((point) => ({ date: point.reportDate, value: point.value }))}
                unit={trendParameter?.unit ?? ''}
                label={trendParameter?.displayName ?? trendKey ?? ''}
              />
            </Card>
          )}

          <Card className={styles.resultCard} title="What changed">
            <p className={styles.narrative}>
              {result.narrative || 'A plain-language summary is unavailable right now; the comparison above still applies.'}
            </p>
          </Card>

          <Card
            className={styles.resultCard}
            title="Share with your doctor"
            subtitle="Creates a doctor-review PDF behind a revocable link that expires in 24 hours."
            actions={
              <Button variant="secondary" onClick={() => shareMutation.mutate()} isLoading={shareMutation.isPending}>
                Create doctor PDF
              </Button>
            }
          >
            {share ? (
              <p className={styles.narrative}>
                <a href={absoluteApiUrl(share.shareUrl)} target="_blank" rel="noreferrer noopener">
                  Open the shareable doctor PDF
                </a>{' '}
                - link expires {new Date(share.expiresAt).toLocaleString()}. Anyone with this link can view the
                document, so share it only with your clinician.
              </p>
            ) : (
              <p className={styles.narrative}>
                The PDF carries the comparison table, the summary, and a doctor sign-off section.
              </p>
            )}
          </Card>
        </>
      )}
    </section>
  );
}
