/**
 * Small vector "product" illustration for a comparison card (blister strip / capsule / bottle).
 * Deliberately illustrated rather than a photo of real packaging - there is no licensed source
 * of per-manufacturer product photography, and real branded packaging would risk trademark/
 * copyright issues. Color is derived deterministically from the brand+manufacturer label so
 * each card still reads as visually distinct.
 */

const PALETTE = ['#22c55e', '#14b8a6', '#4f46e5', '#f59e0b', '#ec4899', '#0ea5e9', '#a855f7'];

function colorForSeed(seed: string): string {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

interface MedicineArtProps {
  seed: string;
  dosageForm?: string | null;
  className?: string;
}

export function MedicineArt({ seed, dosageForm, className }: MedicineArtProps) {
  const color = colorForSeed(seed);
  const form = (dosageForm ?? '').toLowerCase();
  const isCapsule = form.includes('cap');
  const isLiquid = form.includes('syrup') || form.includes('liquid') || form.includes('drop');

  if (isLiquid) {
    return (
      <svg viewBox="0 0 200 96" className={className} role="presentation" focusable="false" style={{ color }}>
        <rect width="200" height="96" rx="14" fill="currentColor" opacity="0.12" />
        <rect x="82" y="14" width="36" height="14" rx="4" fill="currentColor" opacity="0.55" />
        <path
          d="M78 28h44l6 14v38a8 8 0 0 1-8 8H80a8 8 0 0 1-8-8V42z"
          fill="currentColor"
          opacity="0.85"
        />
        <rect x="76" y="58" width="48" height="16" fill="rgba(255,255,255,0.55)" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 200 96" className={className} role="presentation" focusable="false" style={{ color }}>
      <rect width="200" height="96" rx="14" fill="currentColor" opacity="0.12" />
      <rect x="6" y="8" width="188" height="2" rx="1" fill="currentColor" opacity="0.3" />
      {Array.from({ length: 5 }).map((_, index) => (
        <g key={index} transform={`translate(${24 + index * 34} 52)`}>
          {isCapsule ? (
            <rect x="-13" y="-9" width="26" height="18" rx="9" fill="currentColor" opacity="0.85" />
          ) : (
            <circle r="11" fill="currentColor" opacity="0.85" />
          )}
          <circle r="2.6" fill="rgba(255,255,255,0.85)" />
        </g>
      ))}
    </svg>
  );
}
