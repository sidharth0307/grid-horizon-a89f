const mwFormat = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const signedMwFormat = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0, signDisplay: 'exceptZero' });

export const DASH = '—';

/** 2041.96 -> "2,042" */
export function formatMw(value: number | null | undefined): string {
  return value === null || value === undefined ? DASH : mwFormat.format(value);
}

/** 1747.89 -> "+1,748", -50 -> "-50" */
export function formatSignedMw(value: number | null | undefined): string {
  return value === null || value === undefined ? DASH : signedMwFormat.format(value);
}

/** 15.22 -> "15.2%" */
export function formatPct(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? DASH : `${value.toFixed(digits)}%`;
}

/** 15.22 -> "−15.2% MAE" (an improvement); -3 -> "+3.0% MAE" (worse). */
export function formatMaeChange(improvementPct: number): string {
  const sign = improvementPct >= 0 ? '−' : '+';
  return `${sign}${Math.abs(improvementPct).toFixed(1)}% MAE`;
}
