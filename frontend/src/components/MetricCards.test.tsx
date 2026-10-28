import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { MetricCards } from './MetricCards';
import { metricsFixture } from './fixtures';

const render = (metrics: Parameters<typeof MetricCards>[0]['metrics'], loading = false) =>
  renderToStaticMarkup(<MetricCards metrics={metrics} loading={loading} />);

describe('MetricCards', () => {
  it('shows four skeleton cards before the first response', () => {
    const html = render(null, true);
    expect(html.match(/animate-pulse/g)).toHaveLength(4);
  });

  it('renders the headline metrics with units and signs', () => {
    const html = render(metricsFixture());
    expect(html).toContain('2,042');       // MAE
    expect(html).toContain('2,509');       // RMSE
    expect(html).toContain('+1,748');      // bias, signed
    expect(html).toContain('4,341');       // P90 shortfall buffer
    expect(html).toContain('18.1%');       // WAPE
    expect(html).toContain('53.0% better than 48h persistence');
    expect(html).toContain('84.7% of half-hours over-forecast');
  });

  it('describes a negative bias as under-forecast', () => {
    const html = render(metricsFixture({ mean_bias_mw: -120, over_forecast_share_pct: 30 }));
    expect(html).toContain('-120');
    expect(html).toContain('Under-forecast tendency');
  });

  it('omits optional lines when the API does not supply them', () => {
    const html = render(metricsFixture({ over_forecast_share_pct: null, skill_score_pct: null }));
    expect(html).not.toContain('over-forecast');
    expect(html).not.toContain('persistence');
  });

  it('keeps showing the previous values, dimmed, while a new request is loading', () => {
    const html = render(metricsFixture(), true);
    expect(html).toContain('2,042');
    expect(html).toContain('opacity-50');
    expect(html).toContain('aria-busy="true"');
  });
});
