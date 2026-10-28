// Evaluation scope: purchase decisions made 1-31 Jan 2026 -> delivery 2 Jan 00:00 to 1 Feb 23:30 (UTC).
export const SCOPE_FROM = '2026-01-02T00:00:00Z';
export const SCOPE_TO = '2026-02-01T23:30:00Z';
export const DECISION_MIN = '2026-01-01';
export const DECISION_MAX = '2026-01-31';

export type ViewMode = 'month' | 'day';

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** True for a real calendar date inside the January 2026 decision window. */
export function isValidDecisionDate(value: string): boolean {
  if (!ISO_DATE.test(value)) return false;
  if (value < DECISION_MIN || value > DECISION_MAX) return false;
  return !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
}

/** Delivery date is the day after the decision date. Pure UTC arithmetic: no dependence on the browser timezone. */
export function deliveryDateFor(decisionDate: string): string {
  const d = new Date(`${decisionDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export function windowFor(mode: ViewMode, decisionDate: string): { dateFrom: string; dateTo: string } {
  if (mode === 'month') return { dateFrom: SCOPE_FROM, dateTo: SCOPE_TO };
  const delivery = deliveryDateFor(decisionDate);
  return { dateFrom: `${delivery}T00:00:00Z`, dateTo: `${delivery}T23:30:00Z` };
}

const LONDON = 'Europe/London';
const stampFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
});
const clockFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON, hour: '2-digit', minute: '2-digit', hour12: false,
});

/** e.g. "5 Jan, 07:30" in Europe/London time, whatever the viewer's own timezone. */
export function formatLondon(iso: string): string {
  return stampFormat.format(new Date(iso));
}

/** e.g. "07:30" in Europe/London time. */
export function londonClock(iso: string): string {
  return clockFormat.format(new Date(iso));
}

/** The forecast issue time (London clock) used by most periods in the series, or null if none. */
export function dominantRun(series: ReadonlyArray<{ publishTime?: string | null }>): string | null {
  const counts = new Map<string, number>();
  for (const point of series) {
    if (!point.publishTime) continue;
    const clock = londonClock(point.publishTime);
    counts.set(clock, (counts.get(clock) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [clock, count] of counts) {
    if (count > bestCount) { best = clock; bestCount = count; }
  }
  return best;
}
