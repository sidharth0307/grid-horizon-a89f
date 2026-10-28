import { describe, expect, it } from 'vitest';
import { DASH, formatMaeChange, formatMw, formatPct, formatSignedMw } from './format';

describe('number formatting', () => {
  it('rounds MW to whole numbers with thousands separators', () => {
    expect(formatMw(2041.96)).toBe('2,042');
    expect(formatMw(0)).toBe('0');
  });
  it('signs positive and negative MW, but not zero', () => {
    expect(formatSignedMw(1747.89)).toBe('+1,748');
    expect(formatSignedMw(-50.2)).toBe('-50');
    expect(formatSignedMw(0)).toBe('0');
  });
  it('renders missing values as a dash', () => {
    expect(formatMw(null)).toBe(DASH);
    expect(formatMw(undefined)).toBe(DASH);
    expect(formatSignedMw(null)).toBe(DASH);
    expect(formatPct(null)).toBe(DASH);
  });
  it('formats percentages with one decimal', () => {
    expect(formatPct(15.22)).toBe('15.2%');
    expect(formatPct(84.7)).toBe('84.7%');
  });
});

describe('formatMaeChange', () => {
  it('shows an improvement as a reduction', () => {
    expect(formatMaeChange(15.22)).toBe('−15.2% MAE');
  });
  it('shows a regression as an increase', () => {
    expect(formatMaeChange(-3)).toBe('+3.0% MAE');
  });
});
