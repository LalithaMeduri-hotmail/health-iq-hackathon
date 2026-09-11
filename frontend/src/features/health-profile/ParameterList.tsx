/**
 * Plain-language view of a lab value: the number, how it compares to the typical range, and a
 * meter that shows at a glance how far outside that range it sits.
 */

import { Badge } from '@/components/ui';

import { statusLabel, statusTone } from './status';
import styles from './health-profile.module.css';
import type { LabParameter } from './types';

/** Position of the value and the typical band on a 0-100 meter, or null when no range is on file. */
function meter(parameter: LabParameter) {
  const { refLow, refHigh, value } = parameter;
  if (refLow === null || refHigh === null || refHigh <= refLow) {
    return null;
  }
  const padding = (refHigh - refLow) * 0.75;
  const low = Math.min(refLow - padding, value);
  const high = Math.max(refHigh + padding, value);
  // Extra headroom keeps the marker fully visible when the value sits at either extreme.
  const span = high - low;
  const min = low - span * 0.08;
  const max = high + span * 0.08;
  const scale = (input: number) => ((input - min) / (max - min)) * 100;

  return { bandStart: scale(refLow), bandWidth: scale(refHigh) - scale(refLow), marker: scale(value) };
}

function comparison(parameter: LabParameter): string | null {
  const { refLow, refHigh, value, unit } = parameter;
  if (refHigh !== null && value > refHigh) {
    return `${Number((value - refHigh).toFixed(2))} ${unit} above the typical maximum of ${refHigh} ${unit}`;
  }
  if (refLow !== null && value < refLow) {
    return `${Number((refLow - value).toFixed(2))} ${unit} below the typical minimum of ${refLow} ${unit}`;
  }
  if (refLow !== null && refHigh !== null) {
    return `Inside the typical range of ${refLow}-${refHigh} ${unit}`;
  }
  return null;
}

export function ParameterList({ parameters }: { parameters: LabParameter[] }) {
  if (parameters.length === 0) {
    return <p className={styles.meta}>Every measured value sits inside its typical range.</p>;
  }

  return (
    <ul className={styles.parameterList}>
      {parameters.map((parameter) => {
        const bar = meter(parameter);
        const note = comparison(parameter);

        return (
          <li key={parameter.canonicalKey} className={styles.parameterCard}>
            <div className={styles.parameterHead}>
              <h4 className={styles.parameterName}>{parameter.displayName}</h4>
              <Badge tone={statusTone(parameter.status)}>{statusLabel(parameter.status)}</Badge>
            </div>

            <p className={styles.parameterValue}>
              {parameter.value} <span className={styles.parameterUnit}>{parameter.unit}</span>
            </p>

            {bar && (
              <div className={styles.meter} aria-hidden="true">
                <span
                  className={styles.meterBand}
                  style={{ left: `${bar.bandStart}%`, width: `${bar.bandWidth}%` }}
                />
                <span className={styles.meterMarker} style={{ left: `${bar.marker}%` }} />
              </div>
            )}

            {note && <p className={styles.meta}>{note}</p>}
            {parameter.meaning && <p className={styles.parameterMeaning}>{parameter.meaning}</p>}
          </li>
        );
      })}
    </ul>
  );
}
