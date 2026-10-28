import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { Header } from './Header';
import { metricsFixture } from './fixtures';
import type { KPIResponse } from '../types/api';

type Props = Parameters<typeof Header>[0];

function render(overrides: Partial<Props> = {}) {
  const props: Props = {
    viewMode: 'month',
    onViewModeChange: vi.fn(),
    decisionDate: '2026-01-14',
    onDecisionDateChange: vi.fn(),
    cutoff: '09:20',
    onCutoffChange: vi.fn(),
    showDebiased: false,
    onToggleDebiased: vi.fn(),
    metrics: metricsFixture(),
    runLabel: '07:30',
    ...overrides,
  };
  return renderToStaticMarkup(<Header {...props} />);
}

describe('Header', () => {
  it('shows the live bias-adjustment gain from the API, not a hard-coded figure', () => {
    const html = render();
    expect(html).toContain('Show bias-adjusted (−15.2% MAE)');
    expect(html).not.toContain('20%');
    expect(render({ metrics: metricsFixture({ debiased_improvement_pct: 9.04 }) })).toContain('−9.0% MAE');
  });

  it('labels the active state', () => {
    expect(render({ showDebiased: true })).toContain('Bias-adjusted ON (−15.2% MAE)');
  });

  it('disables the bias-adjustment button when there is no usable history', () => {
    const none: KPIResponse = metricsFixture({ debiased_improvement_pct: null, debiased_periods: 0 });
    const html = render({ metrics: none });
    expect(html).toContain('Bias adjustment unavailable');
    expect(html).toMatch(/<button[^>]*disabled[^>]*>(?:(?!<\/button>).)*Bias adjustment unavailable/s);
  });

  it('shows the forecast run actually used on the gate badge', () => {
    const html = render();
    expect(html).toContain('Gate locked');
    expect(html).toContain('09:20 UK');
    expect(html).toContain('forecast run 07:30 UK on D-1');
  });

  it('flags the pre-2021 gate as legacy and explains it', () => {
    const html = render({ cutoff: '11:00', runLabel: '09:30' });
    expect(html).toContain('Legacy gate');
    expect(html).toContain('selects the same run as 09:50');
    expect(html).toContain('11:00 UK · pre-2021 timing');
  });

  it('offers exactly the three gate options', () => {
    const options = render().match(/<option /g) ?? [];
    expect(options).toHaveLength(3);
  });

  it('shows the decision-to-delivery mapping in day view, including month rollover', () => {
    const html = render({ viewMode: 'day', decisionDate: '2026-01-31' });
    expect(html).toContain('2026-02-01');
    expect(html).toContain('type="date"');
    expect(render()).not.toContain('type="date"');
  });

  it('shows coverage from the metrics', () => {
    const html = render({ metrics: metricsFixture({ coverage_pct: 97.5, paired_periods: 1450 }) });
    expect(html).toContain('97.5%');
    expect(html).toContain('1,450/1,488');
  });

  it('builds the CSV export link for the visible window and gate', () => {
    const month = render({ cutoff: '09:50' });
    expect(month).toContain('/api/export.csv?');
    expect(month).toContain('gate_cutoff=09%3A50');
    expect(month).toContain('date_from=2026-01-02T00%3A00%3A00Z');
    const day = render({ viewMode: 'day', decisionDate: '2026-01-14' });
    expect(day).toContain('date_from=2026-01-15T00%3A00%3A00Z');
    expect(day).toContain('date_to=2026-01-15T23%3A30%3A00Z');
  });
});
