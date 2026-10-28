import { describe, expect, it } from 'vitest';
import {
  SCOPE_FROM, SCOPE_TO, deliveryDateFor, dominantRun, formatLondon, isValidDecisionDate, londonClock, windowFor,
} from './dates';

describe('isValidDecisionDate', () => {
  it.each(['2026-01-01', '2026-01-14', '2026-01-31'])('accepts %s', (d) => {
    expect(isValidDecisionDate(d)).toBe(true);
  });
  it.each(['', 'banana', '2026-1-5', '2025-12-31', '2026-02-01', '2026-01-32', '2026-02-31', '2026-01-14T00:00'])(
    'rejects %j', (d) => { expect(isValidDecisionDate(d)).toBe(false); },
  );
});

describe('deliveryDateFor', () => {
  it('is the day after the decision date', () => {
    expect(deliveryDateFor('2026-01-14')).toBe('2026-01-15');
    expect(deliveryDateFor('2026-01-01')).toBe('2026-01-02');
  });
  it('crosses the month boundary: the last decision day delivers on 1 February', () => {
    expect(deliveryDateFor('2026-01-31')).toBe('2026-02-01');
  });
});

describe('windowFor', () => {
  it('uses the full evaluation scope for the month view', () => {
    expect(windowFor('month', '2026-01-14')).toEqual({ dateFrom: SCOPE_FROM, dateTo: SCOPE_TO });
  });
  it('covers exactly the 48 half-hours of the delivery day for the day view', () => {
    expect(windowFor('day', '2026-01-31')).toEqual({
      dateFrom: '2026-02-01T00:00:00Z', dateTo: '2026-02-01T23:30:00Z',
    });
  });
});

describe('London time formatting', () => {
  it('shows GMT in winter', () => {
    expect(londonClock('2026-01-05T07:30:00Z')).toBe('07:30');
  });
  it('shows BST in summer, regardless of the viewer timezone', () => {
    expect(londonClock('2026-07-01T06:30:00Z')).toBe('07:30');
  });
  it('formats a full stamp with day, month and clock', () => {
    const stamp = formatLondon('2026-01-05T07:30:00Z');
    expect(stamp).toContain('Jan');
    expect(stamp).toContain('07:30');
  });
});

describe('dominantRun', () => {
  it('returns the most common issue time', () => {
    const series = [
      { publishTime: '2026-01-04T07:30:00Z' },
      { publishTime: '2026-01-04T07:30:00Z' },
      { publishTime: '2026-01-08T09:30:00Z' },
      { publishTime: null },
    ];
    expect(dominantRun(series)).toBe('07:30');
  });
  it('returns null when nothing has an issue time', () => {
    expect(dominantRun([])).toBeNull();
    expect(dominantRun([{ publishTime: null }, {}])).toBeNull();
  });
});
